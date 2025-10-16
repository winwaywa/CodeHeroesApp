# from typing import List, Optional
# from sqlmodel import select
# from domain.ports import ReviewRepositoryPort, ReviewDTO, FixDTO
# from infra.db.engine import get_session
# from infra.db.models import Review, Fix


# class SqlModelReviewRepository(ReviewRepositoryPort):
#     def save_review(self, review: ReviewDTO) -> ReviewDTO:
#         from sqlmodel import Session
#         with next(get_session()) as s: # type: Session
#             obj = Review(language=review.language, model=review.model,
#             code=review.code, review_markdown=review.review_markdown)
#             s.add(obj)
#             s.commit()
#             s.refresh(obj)
#             review.id = obj.id
#             return review


#     def save_fix(self, fix: FixDTO) -> FixDTO:
#         from sqlmodel import Session
#         with next(get_session()) as s: # type: Session
#             obj = Fix(review_id=fix.review_id, fixed_markdown=fix.fixed_markdown,
#             fixed_code=fix.fixed_code)
#             s.add(obj)
#             s.commit()
#             s.refresh(obj)
#             fix.id = obj.id
#             return fix


#     def list_reviews(self, limit: int = 50) -> List[ReviewDTO]:
#         from sqlmodel import Session
#         with next(get_session()) as s: # type: Session
#             rows = s.exec(select(Review).order_by(Review.id.desc()).limit(limit)).all()
#             return [ReviewDTO(id=r.id, language=r.language, model=r.model,
#             code=r.code, review_markdown=r.review_markdown) for r in rows]


#     def get_review(self, review_id: int) -> Optional[ReviewDTO]:
#         from sqlmodel import Session
#         with next(get_session()) as s: # type: Session
#             r = s.get(Review, review_id)
#             if not r:
#                 return None
#             return ReviewDTO(id=r.id, language=r.language, model=r.model,
#             code=r.code, review_markdown=r.review_markdown)