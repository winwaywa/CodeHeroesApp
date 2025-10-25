import logging
import streamlit as st

logging.basicConfig(
    level=logging.INFO,  # đảm bảo log cấp INFO trở lên được in
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]  # in ra stdout
)

logger = logging.getLogger(__name__)


