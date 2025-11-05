import logging
import os
import streamlit as st

# Đảm bảo thư mục tmp tồn tại
os.makedirs("tmp", exist_ok=True)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,  # log cấp INFO trở lên
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        # logging.StreamHandler(),                        # in ra stdout
        logging.FileHandler("tmp/log.txt", encoding="utf-8")  # ghi log vào file
    ]
)

logger = logging.getLogger(__name__)

