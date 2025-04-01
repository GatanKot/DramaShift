import copy
import unittest
from ScoredWrapper import calculate_post_drama_score  # Replace with your actual module


def post_mock(up, down, comm):
    return {"score_up": up, "score_down": down, "comments": comm}


unranked_posts = [
    post_mock(1000, 1000, 100),
    post_mock(100, 100, 100),
    post_mock(5, 5, 100),
    post_mock(50, 50, 50),
    post_mock(1000, 10, 1000),
    post_mock(1000, 10, 100),
    post_mock(10, 90, 50),
    post_mock(90, 10, 50),
    post_mock(100, 100, 10),
    post_mock(50, 50, 10),
    post_mock(10, 10, 1),
    post_mock(3, 1, 1),
    post_mock(0, 0, 0),
]


class TestControversyScore(unittest.TestCase):

    def test_no_engagement(self):
        """Test when there are no votes or comments."""
        self.assertEqual(calculate_post_drama_score(post_mock(0, 0, 0)), 0)

    def test_balanced_votes(self):
        """Test when upvotes and downvotes are equal."""
        self.assertEqual(calculate_post_drama_score(post_mock(100, 100, 40)),
                         calculate_post_drama_score(post_mock(40, 40, 40)))

    def test_controversial_case(self):
        """Test when there are many downvotes relative to upvotes."""
        self.assertGreater(calculate_post_drama_score(post_mock(10, 10, 50)),
                           calculate_post_drama_score(post_mock(10, 90, 50)))

    def test_controversial_case(self):
        """Test when there are many downvotes relative to upvotes."""
        self.assertGreater(calculate_post_drama_score(post_mock(10, 90, 50)),
                           calculate_post_drama_score(post_mock(89, 10, 50)))

    def test_low_vote_high_comments(self):
        """Test when votes are low but comments are high, indicating controversy."""
        self.assertGreater(calculate_post_drama_score(post_mock(15, 15, 100)),
                           calculate_post_drama_score(post_mock(50, 50, 10)))

    def test_print_order(self):
        #  see what order tests end up with.
        local_unranked_posts = copy.deepcopy(unranked_posts)
        for post in local_unranked_posts:
            post["drama_score"] = calculate_post_drama_score(post)

        local_ranked_posts = sorted(local_unranked_posts, key=lambda p: p["drama_score"], reverse=True)
        for post in local_ranked_posts:
            print(f"up: {post['score_up']}\ndown: {post['score_down']}\n"
                  f"comments: {post['comments']}\nscore: {post['drama_score']}")


class TestCommentControversyScore(unittest.TestCase):

    def test_rank_controversial_comments(self):
        print("stub")
        pass


if __name__ == "__main__":
    unittest.main()
