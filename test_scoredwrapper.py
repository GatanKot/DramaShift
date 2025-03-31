import unittest
from ScoredWrapper import calculate_drama_score  # Replace with your actual module


def post_mock(up, down, comm):
    return {"score_up": up, "score_down": down, "comments": comm}


class TestControversyScore(unittest.TestCase):

    def test_no_engagement(self):
        """Test when there are no votes or comments."""
        self.assertEqual(calculate_drama_score(post_mock(0, 0, 0), 100), 0)

    def test_balanced_votes(self):
        """Test when upvotes and downvotes are equal."""
        self.assertGreater(calculate_drama_score(post_mock(100, 100, 10), 100),
                           calculate_drama_score(post_mock(10, 10, 1), 100))

    def test_controversial_case(self):
        """Test when there are many downvotes relative to upvotes."""
        self.assertGreater(calculate_drama_score(post_mock(10, 90, 50), 100),
                           calculate_drama_score(post_mock(10, 10, 50), 100))

    def test_low_vote_high_comments(self):
        """Test when votes are low but comments are high, indicating controversy."""
        self.assertGreater(calculate_drama_score(post_mock(5, 5, 100), 100),
                           calculate_drama_score(post_mock(50, 50, 10), 100))


class TestCommentControversyScore(unittest.TestCase):

    def test_rank_controversial_comments(self):
        print("stub")
        pass


if __name__ == "__main__":
    unittest.main()
