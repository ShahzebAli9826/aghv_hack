import os
import hashlib

try:
    import chromadb
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

try:
    import pypdf
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

SAMPLE_NDMA = """
NATIONAL DISASTER MANAGEMENT AUTHORITY (NDMA) — INDIA
STANDARD OPERATING PROCEDURE: URBAN & RIVERINE FLOOD RESPONSE (BIHAR / GANGA-KOSI BASIN)
1. Early Warning & Triggers: When CWC / GloFAS river discharge exceeds warning thresholds or 5-day antecedent rainfall exceeds 90mm, activate District Emergency Operations Centres (DEOC).
2. Evacuation & Depth Thresholds: Roads with water depth >= 0.30m are impassable to standard civilian vehicles (risk of engine stall and vehicle buoyancy). Deploy NDRF inflatable motorized boats (IRB) for zones with predicted depth > 0.30m.
3. Shelter Allocation: Prioritize vulnerable clusters using Topographic Wetness Index (TWI) and elevation safety scores. Ensure potable water (15L/person/day), ORS packets, chlorine tablets, and female-safe sanitation blocks.
4. SACHET CAP v1.2 Alerting: All public warnings must follow WMO/ITU Common Alerting Protocol (CAP v1.2) in Hindi and English with verified human-in-the-loop (HITL) authorization.
"""

SAMPLE_UNOCHA = """
UN OFFICE FOR THE COORDINATION OF HUMANITARIAN AFFAIRS (UN-OCHA)
SOUTH ASIA MONSOON FLASH UPDATE & CLUSTER COORDINATION PROTOCOL
1. Situation Overview: Multimodal SAR (Sentinel-1) and Optical (Sentinel-2) fusion confirms active floodplain inundation across low-lying alluvial depressions.
2. WASH & Health Cluster: Standing water > 24 hours elevates waterborne disease risk (cholera, leptospirosis, dengue). Deploy mobile medical teams and halogen tablets to all primary relief camps.
3. Logistics & Access: Verify time-varying road passability before dispatching relief trucks. Bypass low-lying culverts projected to submerge within 30-60 minutes.
"""

SAMPLE_ASSAM_SDMA = """
ASSAM STATE DISASTER MANAGEMENT AUTHORITY (ASDMA)
BRAHMAPUTRA & BARAK VALLEY FLOOD CONTINGENCY PLAN (MAJULI / JORHAT / KAZIRANGA)
1. Embankment & Breach Monitoring: Monitor high-velocity braided channel erosion along Majuli and Jorhat sectors.
2. Highland & Relief Camp Activation: Activate designated raised multi-purpose flood shelters and school buildings above 60m ASL.
3. Livestock & Vulnerable Groups: Prioritize evacuation of pregnant women, elderly citizens, children, and livestock to raised platforms (Highlands).
"""


class FloodVectorDB:
    def __init__(self, db_path="./chroma_data", corpus_path="./corpus"):
        self.db_path = db_path
        self.corpus_path = corpus_path
        self.has_chroma = HAS_CHROMA

        os.makedirs(db_path, exist_ok=True)
        os.makedirs(corpus_path, exist_ok=True)
        self._ensure_default_samples()

        if self.has_chroma:
            try:
                self.client = chromadb.PersistentClient(path=db_path)
                self.collection = self.client.get_or_create_collection(
                    name="flood_situation_reports"
                )
                self.ingest_corpus_files()
            except Exception as e:
                print(f"[RAG Database] Client initialization failed: {e}. Running in fallback mode.")
                self.has_chroma = False
        else:
            print("[RAG Database Sandbox] ChromaDB not installed. Using in-memory SOP templates.")

    def _ensure_default_samples(self):
        defaults = {
            "ndma_bihar_sop.txt": SAMPLE_NDMA,
            "un_ocha_southasia.txt": SAMPLE_UNOCHA,
            "assam_sdma_contingency.txt": SAMPLE_ASSAM_SDMA,
        }
        for fname, text in defaults.items():
            fpath = os.path.join(self.corpus_path, fname)
            if not os.path.exists(fpath):
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(text.strip() + "\n")

    def extract_text_from_pdf(self, pdf_path):
        text = ""
        if not HAS_PDF:
            return text
        try:
            reader = pypdf.PdfReader(pdf_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        except Exception as e:
            print(f"[RAG Database] Error parsing PDF {pdf_path}: {e}")
        return text

    def chunk_text(self, text, chunk_size=350, overlap=75):
        chunks = []
        words = text.split()
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + chunk_size])
            chunks.append(chunk)
            i += max(1, (chunk_size - overlap))
        return [c for c in chunks if len(c.strip()) > 30]

    def ingest_corpus_files(self):
        """
        Incremental SHA-256 hash-based indexing (Solves P16).
        New or modified files in ./corpus are automatically upserted on startup
        without skipping when collection.count() > 0.
        """
        if not self.has_chroma:
            return

        try:
            existing_ids = set()
            try:
                existing_data = self.collection.get(include=[])
                existing_ids = set(existing_data.get("ids", []))
            except Exception:
                pass

            files = sorted(os.listdir(self.corpus_path))
            new_upserts = 0

            for filename in files:
                filepath = os.path.join(self.corpus_path, filename)
                if not os.path.isfile(filepath):
                    continue
                ext = os.path.splitext(filename)[1].lower()

                raw_text = ""
                if ext in [".txt", ".md"]:
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            raw_text = f.read()
                    except Exception as e:
                        print(f"Error reading file {filename}: {e}")
                elif ext == ".pdf":
                    raw_text = self.extract_text_from_pdf(filepath)

                if not raw_text.strip():
                    continue

                file_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:10]
                chunks = self.chunk_text(raw_text)

                documents, metadatas, ids = [], [], []
                for index, chunk in enumerate(chunks):
                    doc_id = f"doc_{filename}_{file_hash}_{index}"
                    if doc_id not in existing_ids:
                        documents.append(chunk)
                        metadatas.append({"source": filename, "chunk_index": index, "sha256": file_hash})
                        ids.append(doc_id)

                if documents:
                    self.collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
                    new_upserts += len(documents)

            print(
                f"[RAG Database] Incremental index sync complete (+{new_upserts} new chunks, "
                f"total={self.collection.count()})."
            )
        except Exception as e:
            print(f"[RAG Database] Incremental ingestion failed: {e}")

    def query_similar_reports(self, query_text, n_results=3):
        if not self.has_chroma:
            return [
                {"content": SAMPLE_NDMA, "metadata": {"source": "ndma_bihar_sop.txt", "chunk_index": 0}},
                {"content": SAMPLE_UNOCHA, "metadata": {"source": "un_ocha_southasia.txt", "chunk_index": 0}},
                {"content": SAMPLE_ASSAM_SDMA, "metadata": {"source": "assam_sdma_contingency.txt", "chunk_index": 0}},
            ][:n_results]

        try:
            results = self.collection.query(query_texts=[query_text], n_results=n_results)
            formatted_results = []
            if results and "documents" in results and len(results["documents"]) > 0:
                docs = results["documents"][0]
                metas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else [{}] * len(docs)
                for doc, meta in zip(docs, metas):
                    formatted_results.append({"content": doc, "metadata": meta})
            return formatted_results
        except Exception as e:
            print(f"[RAG Database] Query error: {e}")
            return [{"content": SAMPLE_NDMA, "metadata": {"source": "ndma_bihar_sop.txt", "chunk_index": 0}}]
