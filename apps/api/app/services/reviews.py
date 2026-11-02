"""Review eligibility and validation rules."""
def validate_review_rating(rating: int) -> None:
    if rating < 1 or rating > 5:
        raise ValueError("Rating must be between 1 and 5")

def normalize_comment(comment: str) -> str:
    return comment.strip()
