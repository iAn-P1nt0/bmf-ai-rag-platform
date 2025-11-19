"""
Chunk Orchestrator - Creates semantic chunks and ingests to AgentSet.
Schedule: Daily 03:30 IST

Implements AGENTS.md Section 2 requirements:
- Build structure-aware chunks (max 1,200 tokens, 20-30% overlap)
- Attach metadata per chunking.yml
- Push to AgentSet ingestion API
- Track versioning + diff stats
"""
import json
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml
from loguru import logger
import tiktoken

try:
    # AgentSet SDK (placeholder - install with: pip install agentset-sdk)
    # from agentset import AgentSetClient
    AGENTSET_AVAILABLE = False
except ImportError:
    AGENTSET_AVAILABLE = False
    logger.warning("AgentSet SDK not installed. Using mock implementation.")


class ChunkOrchestrator:
    """Agent responsible for creating and ingesting chunks to vector store."""

    def __init__(
        self,
        input_dir: str = "./data/processed",
        chunking_config_path: str = "./configs/chunking/chunking.yml",
        metadata_schema_path: str = "./configs/metadata_schema/metadata_schema.json",
        diff_db_path: str = "./data/cache/bmf_diff.db",
        agentset_api_key: Optional[str] = None,
        agentset_index: str = "bmf-rag-v1"
    ):
        """
        Initialize Chunk Orchestrator.

        Args:
            input_dir: Directory containing parsed documents
            chunking_config_path: Path to chunking.yml
            metadata_schema_path: Path to metadata_schema.json
            diff_db_path: Path to SQLite diff database
            agentset_api_key: AgentSet API key
            agentset_index: AgentSet index name
        """
        self.input_dir = Path(input_dir)
        self.chunking_config_path = Path(chunking_config_path)
        self.metadata_schema_path = Path(metadata_schema_path)
        self.diff_db_path = Path(diff_db_path)
        self.agentset_index = agentset_index

        # Load configurations
        self.chunking_config = self._load_chunking_config()
        self.metadata_schema = self._load_metadata_schema()

        # Initialize tokenizer (using tiktoken for token counting)
        self.encoding = tiktoken.get_encoding("cl100k_base")

        # Initialize diff database
        self._init_diff_db()

        # Initialize AgentSet client (mock for now)
        if AGENTSET_AVAILABLE and agentset_api_key:
            # self.agentset_client = AgentSetClient(api_key=agentset_api_key)
            pass
        else:
            self.agentset_client = None
            logger.info("Using mock AgentSet client")

        self.stats = {
            'total_documents': 0,
            'total_chunks': 0,
            'new_chunks': 0,
            'updated_chunks': 0,
            'unchanged_chunks': 0,
            'failed_chunks': 0
        }

    def _load_chunking_config(self) -> Dict:
        """Load chunking configuration."""
        with open(self.chunking_config_path, 'r') as f:
            return yaml.safe_load(f)

    def _load_metadata_schema(self) -> Dict:
        """Load metadata schema."""
        with open(self.metadata_schema_path, 'r') as f:
            return json.load(f)

    def _init_diff_db(self):
        """Initialize SQLite database for tracking chunk versions."""
        self.diff_db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.diff_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunk_checksums (
                chunk_id TEXT PRIMARY KEY,
                parent_document_id TEXT,
                checksum TEXT,
                version INTEGER,
                created_at TEXT,
                updated_at TEXT,
                ingested_at TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))

    def create_chunks(self, document: Dict) -> List[Dict]:
        """
        Create structure-aware chunks from parsed document.

        Args:
            document: Parsed document dictionary

        Returns:
            List of chunk dictionaries
        """
        logger.info(f"Creating chunks for document: {document.get('source_file')}")

        chunks = []

        # Get chunking parameters
        max_tokens = self.chunking_config['token_limits']['max_tokens_per_chunk']
        overlap_pct = self.chunking_config['overlap']['percentage'] / 100
        overlap_tokens = int(max_tokens * overlap_pct)

        # Extract content based on file type
        if document.get('file_type') == 'html':
            chunks = self._chunk_html_document(document, max_tokens, overlap_tokens)
        elif document.get('file_type') == 'pdf':
            chunks = self._chunk_pdf_document(document, max_tokens, overlap_tokens)
        else:
            logger.warning(f"Unknown file type: {document.get('file_type')}")
            return []

        logger.info(f"Created {len(chunks)} chunks from document")

        return chunks

    def _chunk_html_document(
        self,
        document: Dict,
        max_tokens: int,
        overlap_tokens: int
    ) -> List[Dict]:
        """Create chunks from HTML document."""
        chunks = []

        # Use semantic elements if available (from Unstructured.io)
        if document.get('semantic_elements'):
            chunks = self._chunk_semantic_elements(
                document['semantic_elements'],
                max_tokens,
                overlap_tokens,
                document
            )
        else:
            # Fall back to plain text chunking
            chunks = self._chunk_plain_text(
                document.get('plain_text', ''),
                max_tokens,
                overlap_tokens,
                document
            )

        # Handle tables separately (preserve verbatim per chunking.yml)
        if document.get('tables') and self.chunking_config['table_handling']['preserve_verbatim']:
            table_chunks = self._create_table_chunks(document['tables'], document)
            chunks.extend(table_chunks)

        return chunks

    def _chunk_pdf_document(
        self,
        document: Dict,
        max_tokens: int,
        overlap_tokens: int
    ) -> List[Dict]:
        """Create chunks from PDF document preserving page structure."""
        chunks = []

        # Process page by page
        for page in document.get('pages', []):
            page_text = '\n'.join(
                elem['text'] for elem in page.get('elements', [])
            )

            page_chunks = self._chunk_plain_text(
                page_text,
                max_tokens,
                overlap_tokens,
                document,
                extra_metadata={'page_number': page['page_number']}
            )

            chunks.extend(page_chunks)

        return chunks

    def _chunk_semantic_elements(
        self,
        elements: List[Dict],
        max_tokens: int,
        overlap_tokens: int,
        document: Dict
    ) -> List[Dict]:
        """Chunk based on semantic elements from Unstructured.io."""
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_index = 0

        for elem in elements:
            elem_text = elem.get('text', '')
            elem_tokens = self.count_tokens(elem_text)

            # If element alone exceeds max, split it
            if elem_tokens > max_tokens:
                # Flush current chunk
                if current_chunk:
                    chunks.append(self._create_chunk_dict(
                        ' '.join(current_chunk),
                        chunk_index,
                        document
                    ))
                    chunk_index += 1
                    current_chunk = []
                    current_tokens = 0

                # Split large element
                split_chunks = self._split_large_text(elem_text, max_tokens, overlap_tokens)
                for split_text in split_chunks:
                    chunks.append(self._create_chunk_dict(
                        split_text,
                        chunk_index,
                        document
                    ))
                    chunk_index += 1

            # Can we add this element to current chunk?
            elif current_tokens + elem_tokens <= max_tokens:
                current_chunk.append(elem_text)
                current_tokens += elem_tokens
            else:
                # Flush current chunk with overlap
                chunks.append(self._create_chunk_dict(
                    ' '.join(current_chunk),
                    chunk_index,
                    document
                ))
                chunk_index += 1

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk, overlap_tokens)
                current_chunk = [overlap_text, elem_text] if overlap_text else [elem_text]
                current_tokens = self.count_tokens(' '.join(current_chunk))

        # Flush final chunk
        if current_chunk:
            chunks.append(self._create_chunk_dict(
                ' '.join(current_chunk),
                chunk_index,
                document
            ))

        return chunks

    def _chunk_plain_text(
        self,
        text: str,
        max_tokens: int,
        overlap_tokens: int,
        document: Dict,
        extra_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """Chunk plain text with overlapping windows."""
        chunks = []

        # Split by paragraphs first
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        current_chunk = []
        current_tokens = 0
        chunk_index = 0

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            # Handle very long paragraphs that exceed max_tokens
            if para_tokens > max_tokens:
                # Split long paragraph by sentences/words
                logger.warning(f"Paragraph exceeds max tokens ({para_tokens} > {max_tokens}), splitting by words")

                # Save current chunk first if it has content
                if current_chunk:
                    chunks.append(self._create_chunk_dict(
                        '\n\n'.join(current_chunk),
                        chunk_index,
                        document,
                        extra_metadata
                    ))
                    chunk_index += 1
                    current_chunk = []
                    current_tokens = 0

                # Split the long paragraph into word-based chunks
                words = para.split()
                word_chunk = []
                word_chunk_tokens = 0

                for word in words:
                    word_tokens = self.count_tokens(word + ' ')
                    if word_chunk_tokens + word_tokens <= max_tokens:
                        word_chunk.append(word)
                        word_chunk_tokens += word_tokens
                    else:
                        if word_chunk:
                            chunks.append(self._create_chunk_dict(
                                ' '.join(word_chunk),
                                chunk_index,
                                document,
                                extra_metadata
                            ))
                            chunk_index += 1
                        word_chunk = [word]
                        word_chunk_tokens = word_tokens

                # Add remaining words as a chunk
                if word_chunk:
                    current_chunk = [' '.join(word_chunk)]
                    current_tokens = word_chunk_tokens

            elif current_tokens + para_tokens <= max_tokens:
                current_chunk.append(para)
                current_tokens += para_tokens
            else:
                # Save current chunk
                if current_chunk:
                    chunks.append(self._create_chunk_dict(
                        '\n\n'.join(current_chunk),
                        chunk_index,
                        document,
                        extra_metadata
                    ))
                    chunk_index += 1

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk, overlap_tokens)
                current_chunk = [overlap_text, para] if overlap_text else [para]
                current_tokens = self.count_tokens('\n\n'.join(current_chunk))

        # Flush final chunk
        if current_chunk:
            chunks.append(self._create_chunk_dict(
                '\n\n'.join(current_chunk),
                chunk_index,
                document,
                extra_metadata
            ))

        return chunks

    def _split_large_text(self, text: str, max_tokens: int, overlap_tokens: int) -> List[str]:
        """Split large text into smaller chunks."""
        words = text.split()
        chunks = []
        current_chunk = []
        current_tokens = 0

        for word in words:
            word_tokens = self.count_tokens(word)

            if current_tokens + word_tokens <= max_tokens:
                current_chunk.append(word)
                current_tokens += word_tokens
            else:
                chunks.append(' '.join(current_chunk))

                # Overlap
                overlap_words = int(len(current_chunk) * overlap_tokens / max_tokens)
                current_chunk = current_chunk[-overlap_words:] + [word] if overlap_words else [word]
                current_tokens = self.count_tokens(' '.join(current_chunk))

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def _get_overlap_text(self, chunks: List[str], overlap_tokens: int) -> str:
        """Get overlap text from end of current chunk."""
        combined = ' '.join(chunks)
        words = combined.split()

        # Take last N words to approximate overlap_tokens
        overlap_words = max(1, overlap_tokens // 2)  # Rough approximation
        return ' '.join(words[-overlap_words:]) if len(words) > overlap_words else combined

    def _create_table_chunks(self, tables: List[Dict], document: Dict) -> List[Dict]:
        """Create chunks from tables (preserved verbatim)."""
        chunks = []

        for idx, table in enumerate(tables):
            # Use markdown representation
            table_content = table.get('markdown', str(table.get('json', '')))

            chunk = {
                'chunk_id': self._generate_chunk_id(document, f"table_{idx}"),
                'content': table_content,
                'metadata': {
                    'parent_document_id': document.get('checksum'),
                    'source_url': document.get('source_file', ''),
                    'section': document.get('section'),
                    'file_type': document.get('file_type'),
                    'has_table': True,
                    'table_index': idx,
                    'table_rows': table.get('rows'),
                    'table_columns': table.get('columns'),
                    'chunk_index': idx,
                    'created_at': datetime.now(timezone.utc).isoformat()
                },
                'token_count': self.count_tokens(table_content)
            }

            chunks.append(chunk)

        return chunks

    def _create_chunk_dict(
        self,
        content: str,
        chunk_index: int,
        document: Dict,
        extra_metadata: Optional[Dict] = None
    ) -> Dict:
        """Create chunk dictionary with metadata."""
        chunk_id = self._generate_chunk_id(document, chunk_index)

        # Build metadata according to schema
        metadata = {
            'chunk_id': chunk_id,
            'parent_document_id': document.get('checksum'),
            'source_url': document.get('source_file', ''),
            'section': document.get('section'),
            'file_type': document.get('file_type'),
            'chunk_index': chunk_index,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'has_table': False,
            'has_financial_metrics': self._detect_financial_metrics(content)
        }

        # Add extracted data from document
        if document.get('extracted_data'):
            metadata.update({
                key: value for key, value in document['extracted_data'].items()
                if key in ['fund_name', 'nav_value', 'aum', 'risk_profile']
            })

        # Add extra metadata
        if extra_metadata:
            metadata.update(extra_metadata)

        # Calculate checksum
        checksum = hashlib.sha256(content.encode()).hexdigest()

        chunk = {
            'chunk_id': chunk_id,
            'content': content,
            'metadata': metadata,
            'checksum': checksum,
            'token_count': self.count_tokens(content)
        }

        return chunk

    def _generate_chunk_id(self, document: Dict, chunk_index) -> str:
        """Generate unique chunk ID."""
        import uuid
        doc_id = document.get('checksum', '')
        unique_str = f"{doc_id}_{chunk_index}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_str))

    def _detect_financial_metrics(self, content: str) -> bool:
        """Detect if chunk contains financial metrics."""
        financial_keywords = [
            'nav', 'aum', 'return', 'cagr', 'yield', 'ratio',
            'crore', 'lakh', 'rupee', '%', 'performance'
        ]
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in financial_keywords)

    def check_chunk_diff(self, chunk: Dict) -> Tuple[str, int]:
        """
        Check if chunk is new, updated, or unchanged.

        Args:
            chunk: Chunk dictionary

        Returns:
            Tuple of (status, version) where status is 'new', 'updated', or 'unchanged'
        """
        chunk_id = chunk['chunk_id']
        checksum = chunk['checksum']

        conn = sqlite3.connect(self.diff_db_path)
        cursor = conn.cursor()

        cursor.execute(
            'SELECT checksum, version FROM chunk_checksums WHERE chunk_id = ?',
            (chunk_id,)
        )

        result = cursor.fetchone()
        conn.close()

        if result is None:
            return ('new', 1)
        elif result[0] != checksum:
            return ('updated', result[1] + 1)
        else:
            return ('unchanged', result[1])

    def update_chunk_checksum(self, chunk: Dict, version: int):
        """Update chunk checksum in diff database."""
        conn = sqlite3.connect(self.diff_db_path)
        cursor = conn.cursor()

        now = datetime.now(timezone.utc).isoformat()

        cursor.execute('''
            INSERT OR REPLACE INTO chunk_checksums
            (chunk_id, parent_document_id, checksum, version, created_at, updated_at, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            chunk['chunk_id'],
            chunk['metadata'].get('parent_document_id'),
            chunk['checksum'],
            version,
            chunk['metadata'].get('created_at'),
            now,
            now
        ))

        conn.commit()
        conn.close()

    def ingest_to_agentset(self, chunks: List[Dict]) -> Dict:
        """
        Ingest chunks to AgentSet vector store.

        Args:
            chunks: List of chunk dictionaries

        Returns:
            Ingestion result
        """
        logger.info(f"Ingesting {len(chunks)} chunks to AgentSet index '{self.agentset_index}'")

        if self.agentset_client:
            # Real AgentSet ingestion
            try:
                # result = self.agentset_client.ingest(
                #     index=self.agentset_index,
                #     documents=[
                #         {
                #             'id': chunk['chunk_id'],
                #             'content': chunk['content'],
                #             'metadata': chunk['metadata']
                #         }
                #         for chunk in chunks
                #     ]
                # )
                pass
            except Exception as e:
                logger.error(f"AgentSet ingestion failed: {e}")
                return {'status': 'error', 'error': str(e)}
        else:
            # Mock ingestion
            logger.info("Mock ingestion (AgentSet SDK not available)")
            result = {
                'status': 'success',
                'index': self.agentset_index,
                'chunks_ingested': len(chunks),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

        return result

    def process_document(self, document_path: Path) -> Dict:
        """
        Process a single parsed document: create chunks and ingest.

        Args:
            document_path: Path to parsed JSON document

        Returns:
            Processing result
        """
        logger.info(f"Processing document: {document_path.name}")

        try:
            with open(document_path, 'r') as f:
                document = json.load(f)

            # Create chunks
            chunks = self.create_chunks(document)
            self.stats['total_chunks'] += len(chunks)

            # Check diffs and update stats
            chunks_to_ingest = []
            for chunk in chunks:
                status, version = self.check_chunk_diff(chunk)

                if status == 'new':
                    self.stats['new_chunks'] += 1
                    chunks_to_ingest.append(chunk)
                elif status == 'updated':
                    self.stats['updated_chunks'] += 1
                    chunks_to_ingest.append(chunk)
                else:
                    self.stats['unchanged_chunks'] += 1
                    continue

                # Update checksum
                self.update_chunk_checksum(chunk, version)

            # Ingest to AgentSet
            if chunks_to_ingest:
                ingestion_result = self.ingest_to_agentset(chunks_to_ingest)
            else:
                ingestion_result = {'status': 'skipped', 'reason': 'no_new_chunks'}

            return {
                'document': str(document_path),
                'chunks_created': len(chunks),
                'chunks_ingested': len(chunks_to_ingest),
                'ingestion_result': ingestion_result
            }

        except Exception as e:
            logger.error(f"Failed to process document {document_path}: {e}")
            self.stats['failed_chunks'] += 1
            return {'error': str(e), 'document': str(document_path)}

    def run_orchestrator(self, sections: Optional[List[str]] = None) -> Dict:
        """
        Execute chunk orchestration for all sections.

        Args:
            sections: Optional list of sections to process

        Returns:
            Orchestration report
        """
        logger.info("Starting Chunk Orchestrator run...")

        results = []

        # Find all parsed JSON files
        if sections:
            json_files = []
            for section in sections:
                section_dir = self.input_dir / section
                if section_dir.exists():
                    json_files.extend(section_dir.glob("*.json"))
        else:
            json_files = list(self.input_dir.rglob("*.json"))

        # Filter out report files
        json_files = [f for f in json_files if not f.name.startswith('parser_report')]

        self.stats['total_documents'] = len(json_files)

        logger.info(f"Found {len(json_files)} parsed documents")

        # Process each document
        for json_file in json_files:
            result = self.process_document(json_file)
            results.append(result)

        # Generate report
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'documents_processed': len(json_files),
            'stats': self.stats,
            'results': results
        }

        # Save report
        report_dir = self.input_dir
        report_path = report_dir / f"chunk_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info("Chunk Orchestrator run completed")
        logger.info(f"Stats: {json.dumps(self.stats, indent=2)}")
        logger.info(f"Report saved to {report_path}")

        return report


def main():
    """Main entry point for Chunk Orchestrator."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    input_dir = os.getenv('PARSER_OUTPUT_DIR', './data/processed')
    chunking_config = os.getenv('CHUNKING_CONFIG_PATH', './configs/chunking/chunking.yml')
    metadata_schema = os.getenv('METADATA_SCHEMA_PATH', './configs/metadata_schema/metadata_schema.json')
    diff_db_path = os.getenv('SQLITE_DB_PATH', './data/cache/bmf_diff.db')
    agentset_api_key = os.getenv('AGENTSET_API_KEY')
    agentset_index = os.getenv('AGENTSET_INDEX_NAME', 'bmf-rag-v1')

    orchestrator = ChunkOrchestrator(
        input_dir=input_dir,
        chunking_config_path=chunking_config,
        metadata_schema_path=metadata_schema,
        diff_db_path=diff_db_path,
        agentset_api_key=agentset_api_key,
        agentset_index=agentset_index
    )

    report = orchestrator.run_orchestrator()

    logger.info(f"Chunking completed: {report['stats']}")


if __name__ == "__main__":
    main()
