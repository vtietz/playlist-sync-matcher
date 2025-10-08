"""Unit tests for CandidateSelector."""

import pytest
from psm.match.candidate_selector import CandidateSelector


class TestDurationPrefilter:
    """Test duration-based prefiltering."""
    
    def test_filters_files_outside_window(self):
        """Files outside duration window should be filtered out."""
        selector = CandidateSelector()
        
        track = {'duration_ms': 180000}  # 3 minutes = 180 seconds
        files = [
            {'id': 1, 'duration': 180},  # Exact match
            {'id': 2, 'duration': 183},  # +3s (within ±4s)
            {'id': 3, 'duration': 177},  # -3s (within ±4s)
            {'id': 4, 'duration': 200},  # +20s (outside ±4s)
            {'id': 5, 'duration': 160},  # -20s (outside ±4s)
        ]
        
        result = selector.duration_prefilter(track, files, dur_tolerance=2.0)
        result_ids = [f['id'] for f in result]
        
        assert 1 in result_ids
        assert 2 in result_ids
        assert 3 in result_ids
        assert 4 not in result_ids
        assert 5 not in result_ids
    
    def test_minimum_4_second_window(self):
        """Duration window should be at least ±4 seconds."""
        selector = CandidateSelector()
        
        track = {'duration_ms': 180000}  # 180 seconds
        files = [
            {'id': 1, 'duration': 184},  # +4s (should pass)
            {'id': 2, 'duration': 176},  # -4s (should pass)
            {'id': 3, 'duration': 185},  # +5s (should fail)
            {'id': 4, 'duration': 175},  # -5s (should fail)
        ]
        
        # Even with dur_tolerance=1.0, window should be max(4, 1*2) = 4
        result = selector.duration_prefilter(track, files, dur_tolerance=1.0)
        result_ids = [f['id'] for f in result]
        
        assert 1 in result_ids
        assert 2 in result_ids
        assert 3 not in result_ids
        assert 4 not in result_ids
    
    def test_larger_tolerance_expands_window(self):
        """Larger tolerance should expand the window beyond ±4s."""
        selector = CandidateSelector()
        
        track = {'duration_ms': 180000}  # 180 seconds
        files = [
            {'id': 1, 'duration': 190},  # +10s
            {'id': 2, 'duration': 170},  # -10s
        ]
        
        # dur_tolerance=5.0 -> window = max(4, 5*2) = 10
        result = selector.duration_prefilter(track, files, dur_tolerance=5.0)
        result_ids = [f['id'] for f in result]
        
        assert 1 in result_ids
        assert 2 in result_ids
    
    def test_files_without_duration_always_included(self):
        """Files with no duration metadata should always pass the filter."""
        selector = CandidateSelector()
        
        track = {'duration_ms': 180000}
        files = [
            {'id': 1, 'duration': None},  # No metadata
            {'id': 2, 'duration': 500},   # Way off, but should be filtered
        ]
        
        result = selector.duration_prefilter(track, files, dur_tolerance=2.0)
        result_ids = [f['id'] for f in result]
        
        assert 1 in result_ids  # No duration -> always included
        assert 2 not in result_ids
    
    def test_track_without_duration_returns_all_files(self):
        """If track lacks duration, all files should be returned."""
        selector = CandidateSelector()
        
        track = {'duration_ms': None}
        files = [
            {'id': 1, 'duration': 180},
            {'id': 2, 'duration': 500},
            {'id': 3, 'duration': None},
        ]
        
        result = selector.duration_prefilter(track, files, dur_tolerance=2.0)
        
        assert len(result) == 3  # All files returned
    
    def test_none_tolerance_skips_filtering(self):
        """dur_tolerance=None should return all files."""
        selector = CandidateSelector()
        
        track = {'duration_ms': 180000}
        files = [
            {'id': 1, 'duration': 180},
            {'id': 2, 'duration': 500},
            {'id': 3, 'duration': 10},
        ]
        
        result = selector.duration_prefilter(track, files, dur_tolerance=None)
        
        assert len(result) == 3  # All files returned


class TestTokenPrescore:
    """Test token-based pre-scoring using Jaccard similarity."""
    
    def test_returns_all_if_under_cap(self):
        """If file count < max_candidates, return all without sorting."""
        selector = CandidateSelector()
        
        track = {'normalized': 'artist album title'}
        files = [
            {'id': 1, 'normalized': 'artist album title'},
            {'id': 2, 'normalized': 'different artist'},
        ]
        
        result = selector.token_prescore(track, files, max_candidates=10)
        
        assert len(result) == 2
        # Order may not be guaranteed when no sorting happens
    
    def test_caps_to_max_candidates(self):
        """Should return at most max_candidates files."""
        selector = CandidateSelector()
        
        track = {'normalized': 'artist album title'}
        files = [
            {'id': i, 'normalized': f'artist album title {i}'}
            for i in range(100)
        ]
        
        result = selector.token_prescore(track, files, max_candidates=10)
        
        assert len(result) == 10
    
    def test_prioritizes_higher_similarity(self):
        """Files with higher Jaccard similarity should be ranked first."""
        selector = CandidateSelector()
        
        track = {'normalized': 'pink floyd dark side moon'}
        files = [
            {'id': 1, 'normalized': 'pink floyd dark side moon'},  # Perfect match (1.0)
            {'id': 2, 'normalized': 'pink floyd dark side'},       # 4/5 = 0.8
            {'id': 3, 'normalized': 'pink floyd'},                 # 2/5 = 0.4
            {'id': 4, 'normalized': 'beatles abbey road'},         # 0/7 = 0.0
        ]
        
        result = selector.token_prescore(track, files, max_candidates=3)
        result_ids = [f['id'] for f in result]
        
        # Top 3 should be IDs 1, 2, 3 (in that order)
        assert result_ids == [1, 2, 3]
    
    def test_handles_empty_normalized_fields(self):
        """Should handle empty or missing normalized fields gracefully."""
        selector = CandidateSelector()
        
        track = {'normalized': ''}
        files = [
            {'id': 1, 'normalized': ''},
            {'id': 2, 'normalized': 'some tokens'},
            {'id': 3, 'normalized': None},
        ]
        
        # Should not crash
        result = selector.token_prescore(track, files, max_candidates=10)
        assert len(result) == 3
    
    def test_descending_similarity_order(self):
        """Results should be sorted by similarity descending when over cap."""
        selector = CandidateSelector()
        
        track = {'normalized': 'a b c d'}
        files = [
            {'id': 1, 'normalized': 'a b'},          # 2/4 = 0.5
            {'id': 2, 'normalized': 'a b c'},        # 3/4 = 0.75
            {'id': 3, 'normalized': 'a b c d'},      # 4/4 = 1.0
            {'id': 4, 'normalized': 'a'},            # 1/4 = 0.25
            {'id': 5, 'normalized': 'x y z'},        # 0/7 = 0.0
        ]
        
        # Use max_candidates < len(files) to force sorting
        result = selector.token_prescore(track, files, max_candidates=4)
        result_ids = [f['id'] for f in result]
        
        # Should be ordered by similarity: 3, 2, 1, 4 (5 excluded)
        assert result_ids == [3, 2, 1, 4]


class TestJaccardSimilarity:
    """Test Jaccard similarity calculation."""
    
    def test_identical_sets_return_1_0(self):
        """Identical sets should have similarity of 1.0."""
        selector = CandidateSelector()
        
        set1 = {'a', 'b', 'c'}
        set2 = {'a', 'b', 'c'}
        
        assert selector._jaccard_similarity(set1, set2) == 1.0
    
    def test_disjoint_sets_return_0_0(self):
        """Completely different sets should have similarity of 0.0."""
        selector = CandidateSelector()
        
        set1 = {'a', 'b', 'c'}
        set2 = {'x', 'y', 'z'}
        
        assert selector._jaccard_similarity(set1, set2) == 0.0
    
    def test_partial_overlap(self):
        """Partial overlap should return correct ratio."""
        selector = CandidateSelector()
        
        set1 = {'a', 'b', 'c'}
        set2 = {'b', 'c', 'd'}
        # Intersection: {b, c} = 2
        # Union: {a, b, c, d} = 4
        # Similarity: 2/4 = 0.5
        
        assert selector._jaccard_similarity(set1, set2) == 0.5
    
    def test_empty_sets_return_0_0(self):
        """Empty sets should return 0.0 (avoid division by zero)."""
        selector = CandidateSelector()
        
        assert selector._jaccard_similarity(set(), set()) == 0.0
    
    def test_one_empty_set_returns_0_0(self):
        """If one set is empty, similarity should be 0.0."""
        selector = CandidateSelector()
        
        set1 = {'a', 'b', 'c'}
        set2 = set()
        
        assert selector._jaccard_similarity(set1, set2) == 0.0
        assert selector._jaccard_similarity(set2, set1) == 0.0


class TestCandidateSelectorIntegration:
    """Integration tests combining duration and token filtering."""
    
    def test_realistic_two_stage_filtering(self):
        """Realistic scenario: duration filter then token prescore."""
        selector = CandidateSelector()
        
        track = {
            'duration_ms': 240000,  # 4 minutes
            'normalized': 'led zeppelin stairway heaven'
        }
        
        files = [
            {'id': 1, 'duration': 240, 'normalized': 'led zeppelin stairway heaven'},  # Perfect
            {'id': 2, 'duration': 242, 'normalized': 'led zeppelin stairway heaven'},  # Close
            {'id': 3, 'duration': 180, 'normalized': 'led zeppelin'},                  # Duration fail
            {'id': 4, 'duration': 240, 'normalized': 'pink floyd'},                    # Token fail
            {'id': 5, 'duration': 300, 'normalized': 'led zeppelin stairway heaven'},  # Duration fail
        ]
        
        # Stage 1: Duration filter
        duration_filtered = selector.duration_prefilter(track, files, dur_tolerance=2.0)
        duration_ids = [f['id'] for f in duration_filtered]
        
        assert 1 in duration_ids
        assert 2 in duration_ids
        assert 4 in duration_ids
        assert 3 not in duration_ids  # Duration too short
        assert 5 not in duration_ids  # Duration too long
        
        # Stage 2: Token prescore
        top_candidates = selector.token_prescore(track, duration_filtered, max_candidates=2)
        top_ids = [f['id'] for f in top_candidates]
        
        # Should prioritize 1 and 2 (perfect token matches) over 4
        assert 1 in top_ids
        assert 2 in top_ids
        assert 4 not in top_ids
