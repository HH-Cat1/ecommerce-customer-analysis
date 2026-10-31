"""Create deterministic sample order data for the demo application."""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(2026)
out = Path(__file__).parent / "data" / "sample_orders.csv"
out.parent.mkdir(parents=True, exist_ok=True)

products = {
    "数码": [("无线耳机", 299), ("机械键盘", 459), ("智能手环", 239), ("便携音箱", 399)],
    "家居": [("香薰机", 169), ("收纳架", 129), ("台灯", 219), ("四件套", 369)],
    "美妆": [("保湿精华", 259), ("防晒乳", 119), ("洁面套装", 189), ("面膜礼盒", 149)],
    "食品": [("坚果礼盒", 99), ("咖啡豆", 79), ("茶叶礼盒", 159), ("低糖麦片", 49)],
    "运动": [("瑜伽垫", 139), ("跳绳", 59), ("运动水杯", 89), ("筋膜枪", 329)],
}
regions = ["上海", "北京", "杭州", "深圳", "成都", "南京", "武汉", "广州", "苏州", "西安"]
channels = ["天猫", "京东", "抖音", "小红书"]
weights = [0.34, 0.27, 0.25, 0.14]
start = date(2026, 1, 1)
rows = []
for order_num in range(1, 901):
    day = start + timedelta(days=random.randrange(180))
    customer = f"C{random.randrange(1, 381):04d}"
    order_id = f"O{order_num:06d}"
    channel = random.choices(channels, weights=weights, k=1)[0]
    region = random.choice(regions)
    for _ in range(random.choices([1, 2, 3], weights=[0.72, 0.24, 0.04], k=1)[0]):
        category = random.choice(list(products))
        product, base_price = random.choice(products[category])
        quantity = random.choices([1, 2, 3], weights=[0.76, 0.20, 0.04], k=1)[0]
        seasonal = 1.0 + (0.18 if day.month in (3, 6) else 0)
        price = round(base_price * seasonal * random.uniform(0.90, 1.10), 2)
        rows.append([order_id, day.isoformat(), customer, product, category, quantity, price, channel, region])

with out.open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.writer(handle)
    writer.writerow(["order_id", "order_date", "customer_id", "product_name", "category", "quantity", "unit_price", "channel", "region"])
    writer.writerows(rows)

print(f"Created {len(rows)} order lines at {out}")

