from django.test import SimpleTestCase

from core.ai.knowledge_base import KnowledgeBase
from core.ai.retrieval import retrieve_chunks


class RetrievalTests(SimpleTestCase):
    def setUp(self):
        self.kb = KnowledgeBase.from_data(
            {
                "rag_chunks": [
                    {
                        "chunk_id": "chunk_documents",
                        "text": (
                            "Applicants must prepare the required "
                            "documents before applying."
                        ),
                        "tags": ["documents", "application"],
                        "verification_status": "verified",
                        "source_ids": ["source_1"],
                    },
                    {
                        "chunk_id": "chunk_deadlines",
                        "text": "Check the application deadline before submitting.",
                        "tags": ["deadline", "application"],
                        "verification_status": "unverified",
                        "source_ids": ["source_2"],
                    },
                    {
                        "chunk_id": "chunk_unrelated",
                        "text": "General information about another topic.",
                        "tags": ["unrelated"],
                        "verification_status": "verified",
                        "source_ids": [],
                    },
                ]
            },
            skip_index_build=True,
        )

    def test_retrieves_relevant_chunks(self):
        results = retrieve_chunks(
            "What documents are required?",
            self.kb,
        )

        self.assertTrue(results)
        self.assertEqual(results[0].chunk_id, "chunk_documents")

    def test_returns_no_results_for_unrelated_query(self):
        results = retrieve_chunks(
            "How do I bake a cake?",
            self.kb,
        )

        self.assertEqual(results, [])

    def test_preserves_verification_and_source_metadata(self):
        results = retrieve_chunks(
            "What documents are required?",
            self.kb,
        )

        self.assertTrue(results)

        chunk = results[0].chunk
        self.assertIn("verification_status", chunk)
        self.assertIn("source_ids", chunk)

    def test_rejects_invalid_top_k(self):
        with self.assertRaises(ValueError):
            retrieve_chunks("documents", self.kb, top_k=0)

    def test_blank_query_returns_no_results(self):
        self.assertEqual(retrieve_chunks("   ", self.kb), [])