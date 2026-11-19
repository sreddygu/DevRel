# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

#!/usr/bin/env python3
"""
Simple text similarity implementation as fallback for sentence_transformers
"""

import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SimpleSimilarity:
    """Simple text similarity using TF-IDF and cosine similarity"""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            ngram_range=(1, 2),
            max_features=1000,
            lowercase=True
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Encode texts into vectors using TF-IDF
        
        Args:
            texts: List of text strings
            
        Returns:
            numpy array of shape (len(texts), n_features)
        """
        if not texts:
            return np.array([])

        # Clean texts
        cleaned_texts = [self._clean_text(text) for text in texts]

        # Fit and transform if this is the first call, otherwise just transform
        try:
            vectors = self.vectorizer.transform(cleaned_texts)
        except:
            # First time - need to fit
            vectors = self.vectorizer.fit_transform(cleaned_texts)

        return vectors.toarray()

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""

        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())

        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\-\:]', ' ', text)

        return text.lower()

    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two texts
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0

        try:
            vectors = self.encode([text1, text2])
            if vectors.shape[0] < 2:
                return 0.0

            sim = cosine_similarity([vectors[0]], [vectors[1]])[0][0]
            return float(sim)
        except:
            # Fallback to simple word overlap
            return self._word_overlap_similarity(text1, text2)

    def _word_overlap_similarity(self, text1: str, text2: str) -> float:
        """Fallback similarity based on word overlap"""
        words1 = set(self._clean_text(text1).split())
        words2 = set(self._clean_text(text2).split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0


def test_simple_similarity():
    """Test the simple similarity implementation"""
    print("Testing SimpleSimilarity...")

    sim = SimpleSimilarity()

    # Test cases
    test_cases = [
        ("WiFi connection failed", "WiFi connection error", "High similarity"),
        ("Authentication timeout", "Auth timeout occurred", "Medium similarity"),
        ("Network disconnected", "Power supply issue", "Low similarity"),
        ("", "Some text", "Empty text"),
        ("Same text", "Same text", "Identical text")
    ]

    print("\nSimilarity Test Results:")
    print("-" * 60)

    for text1, text2, description in test_cases:
        score = sim.similarity(text1, text2)
        print(f"{description:20} | {score:.3f} | '{text1}' vs '{text2}'")

    print("\nEncoding Test:")
    texts = ["WiFi connection failed", "Network error occurred", "Authentication timeout"]
    vectors = sim.encode(texts)
    print(f"Encoded {len(texts)} texts into vectors of shape: {vectors.shape}")

    print("\n✓ SimpleSimilarity working correctly!")


if __name__ == "__main__":
    test_simple_similarity()
