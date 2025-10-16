# from datetime import datetime
# from typing import Optional
# from sqlmodel import SQLModel, Field, Column, JSON


# class Review(SQLModel, table=True):
#     id: Optional[int] = Field(default=None, primary_key=True)
#     language: str
#     model: str
#     code: str
#     review_markdown: str
#     created_at: datetime = Field(default_factory=datetime.utcnow)


# class Fix(SQLModel, table=True):
#     id: Optional[int] = Field(default=None, primary_key=True)
#     review_id: Optional[int] = Field(default=None, foreign_key="review.id")
#     fixed_markdown: str
#     fixed_code: str
#     created_at: datetime = Field(default_factory=datetime.utcnow)