# from typing import Generator
# from sqlmodel import create_engine, Session
# import os


# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./code_review.db")
# engine = create_engine(DATABASE_URL, echo=False)


# # Streamlit is sync → use non-async Session
# def get_session() -> Generator[Session, None, None]:
#     with Session(engine) as s:
#         yield s