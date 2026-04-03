"""
ICOM Agent - Data Loader (S0-2)
스마트스토어 주문 CSV/Excel 파일을 읽어 DB에 저장하고,
샘플 인플루언서/상품/캠페인/소셜메트릭 데이터를 생성하는 모듈.

PRD Phase 0: 기보유 1년치 데이터 전처리
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.orm import Session
from shared.db import (
    init_db, SessionLocal,
    Influencer, Product, Campaign, SocialMetric, Order, Prediction,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 1. CSV/Excel Order Loader
# =============================================================================
class OrderDataLoader:
    """Load order data from CSV/Excel files into the orders table."""

    REQUIRED_COLUMNS = ["order_number", "amount", "ordered_at"]

    def __init__(self, session: Session):
        self.session = session

    def load_file(self, file_path: str, campaign_id: int | None = None) -> dict:
        """
        Load orders from a CSV or Excel file.

        Args:
            file_path: Path to CSV/Excel file
            campaign_id: Optional campaign to associate orders with

        Returns:
            dict with loaded/skipped/error counts
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read file
        if path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        elif path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path, encoding="utf-8-sig")
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        if df.empty or len(df) == 0:
            raise ValueError("File is empty — no data to load")

        # Validate required columns
        missing = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        return self._process_dataframe(df, campaign_id)

    def _process_dataframe(self, df: pd.DataFrame, campaign_id: int | None) -> dict:
        """Process and insert order records, skipping duplicates."""
        stats = {"loaded": 0, "skipped_duplicate": 0, "skipped_error": 0}

        # Fetch existing order numbers for dedup
        existing = {
            row[0] for row in
            self.session.query(Order.order_number).all()
        }

        for _, row in df.iterrows():
            try:
                order_number = str(row["order_number"]).strip()
                if not order_number or order_number == "nan":
                    stats["skipped_error"] += 1
                    continue

                if order_number in existing:
                    stats["skipped_duplicate"] += 1
                    continue

                # Parse ordered_at
                ordered_at = pd.to_datetime(row["ordered_at"])

                order = Order(
                    campaign_id=campaign_id,
                    order_number=order_number,
                    amount=Decimal(str(row["amount"])),
                    ordered_at=ordered_at,
                    status=str(row.get("status", "")).strip() or None,
                    delivery_status=str(row.get("delivery_status", "")).strip() or None,
                )
                self.session.add(order)
                existing.add(order_number)
                stats["loaded"] += 1

            except Exception as e:
                logger.warning(f"Error processing row: {e}")
                stats["skipped_error"] += 1

        self.session.commit()
        logger.info(f"Order loading complete: {stats}")
        return stats


# =============================================================================
# 2. Sample Data Generator (for POC)
# =============================================================================
class SampleDataGenerator:
    """
    Generate realistic sample data for POC validation.
    Simulates 1 year of influencer commerce operations.
    """

    def __init__(self, session: Session, seed: int = 42):
        self.session = session
        self.rng = np.random.RandomState(seed)

    def generate_all(
        self,
        n_influencers: int = 20,
        n_products: int = 30,
        n_campaigns: int = 100,
    ) -> dict:
        """Generate full sample dataset."""
        influencers = self._generate_influencers(n_influencers)
        products = self._generate_products(n_products)
        self.session.commit()

        campaigns = self._generate_campaigns(influencers, products, n_campaigns)
        self.session.commit()

        metrics_count = 0
        orders_count = 0
        for campaign in campaigns:
            metrics_count += self._generate_social_metrics(campaign)
            orders_count += self._generate_orders(campaign)
        self.session.commit()

        return {
            "influencers": len(influencers),
            "products": len(products),
            "campaigns": len(campaigns),
            "social_metrics": metrics_count,
            "orders": orders_count,
        }

    def _generate_influencers(self, n: int) -> list[Influencer]:
        categories = ["육아", "뷰티", "리뷰", "패션", "식품", "건강"]
        influencers = []
        for i in range(n):
            followers = int(self.rng.lognormal(mean=10.5, sigma=0.8))
            inf = Influencer(
                instagram_id=f"influencer_{i+1:03d}",
                name=f"인플루언서_{i+1:03d}",
                followers_count=min(followers, 500000),
                category=self.rng.choice(categories),
                avg_conversion_rate=round(self.rng.uniform(0.01, 0.08), 4),
                oauth_connected=int(self.rng.random() > 0.2),  # 80% connected
            )
            self.session.add(inf)
            influencers.append(inf)
        self.session.flush()
        return influencers

    def _generate_products(self, n: int) -> list[Product]:
        categories = ["유아용품", "뷰티", "건강식품", "패션잡화", "생활용품", "식품"]
        products = []
        for i in range(n):
            supply = round(self.rng.uniform(5000, 50000), -2)
            margin = self.rng.uniform(1.3, 2.5)
            prod = Product(
                name=f"상품_{i+1:03d}",
                category=self.rng.choice(categories),
                supply_price=Decimal(str(supply)),
                selling_price=Decimal(str(round(supply * margin, -2))),
                commission_rate=round(self.rng.uniform(0.10, 0.25), 2),
                stock_available=int(self.rng.uniform(100, 2000)),
                lead_time_days=int(self.rng.choice([1, 2, 3, 5, 7])),
            )
            self.session.add(prod)
            products.append(prod)
        self.session.flush()
        return products

    def _generate_campaigns(
        self, influencers: list, products: list, n: int
    ) -> list[Campaign]:
        campaigns = []
        base_date = datetime(2025, 4, 1)

        for i in range(n):
            inf = self.rng.choice(influencers)
            prod = self.rng.choice(products)
            days_offset = int(self.rng.uniform(0, 365))
            posted_at = base_date + timedelta(days=days_offset, hours=int(self.rng.uniform(8, 22)))

            # Simulate performance tiers: 20% hit, 50% medium, 30% low
            tier = self.rng.choice(["hit", "medium", "low"], p=[0.2, 0.5, 0.3])
            if tier == "hit":
                actual_sales = int(self.rng.uniform(300, 2000))
            elif tier == "medium":
                actual_sales = int(self.rng.uniform(50, 300))
            else:
                actual_sales = int(self.rng.uniform(5, 50))

            selling_price = float(prod.selling_price)
            revenue = actual_sales * selling_price

            camp = Campaign(
                influencer_id=inf.id,
                product_id=prod.id,
                post_url=f"https://www.instagram.com/p/sample_{i+1:04d}/",
                post_text=f"공구 오픈! {prod.name} 추천합니다~ 한정수량!",
                posted_at=posted_at,
                status="completed",
                initial_stock=int(self.rng.uniform(100, 1000)),
                actual_sales=actual_sales,
                total_revenue=Decimal(str(round(revenue, 2))),
                roi=round(self.rng.uniform(1, 15), 2) if tier != "low" else round(self.rng.uniform(0.5, 3), 2),
            )
            self.session.add(camp)
            campaigns.append(camp)

        self.session.flush()
        return campaigns

    def _generate_social_metrics(self, campaign: Campaign) -> int:
        """Generate time-series social metrics for a campaign."""
        if campaign.posted_at is None:
            return 0

        actual = campaign.actual_sales or 10
        # Engagement correlates with sales (key assumption for prediction model)
        base_likes = int(actual * self.rng.uniform(2, 8))
        count = 0

        for hours in [1, 3, 6, 12, 24]:
            # Engagement grows logarithmically over time
            time_factor = np.log(hours + 1) / np.log(25)
            noise = self.rng.normal(1.0, 0.15)

            likes = int(base_likes * time_factor * noise)
            comments = int(likes * self.rng.uniform(0.05, 0.15))
            shares = int(likes * self.rng.uniform(0.02, 0.08))
            saves = int(likes * self.rng.uniform(0.10, 0.25))

            metric = SocialMetric(
                campaign_id=campaign.id,
                measured_at=campaign.posted_at + timedelta(hours=hours),
                hours_after_post=float(hours),
                likes=max(likes, 0),
                comments=max(comments, 0),
                shares=max(shares, 0),
                saves=max(saves, 0),
                reach=int(likes * self.rng.uniform(3, 10)),
                impressions=int(likes * self.rng.uniform(5, 15)),
                sentiment_score=round(self.rng.uniform(-0.2, 0.9), 3),
            )
            self.session.add(metric)
            count += 1

        return count

    def _generate_orders(self, campaign: Campaign) -> int:
        """Generate individual order records for a campaign."""
        actual_sales = campaign.actual_sales or 0
        if actual_sales == 0 or campaign.posted_at is None:
            return 0

        selling_price = float(campaign.product.selling_price)
        count = 0

        for j in range(actual_sales):
            # Orders spread across campaign duration (mostly first 24-48h)
            hours_offset = self.rng.exponential(scale=12)
            ordered_at = campaign.posted_at + timedelta(hours=min(hours_offset, 72))

            order = Order(
                campaign_id=campaign.id,
                order_number=f"SS-{campaign.id:04d}-{j+1:05d}",
                amount=Decimal(str(selling_price)),
                ordered_at=ordered_at,
                status="delivered",
                delivery_status="delivered",
            )
            self.session.add(order)
            count += 1

        return count


# =============================================================================
# CLI Entry Point
# =============================================================================
def main():
    """Generate sample data for POC."""
    logging.basicConfig(level=logging.INFO)
    init_db()

    session = SessionLocal()
    try:
        # Check if data already exists
        existing = session.query(Campaign).count()
        if existing > 0:
            logger.info(f"Database already has {existing} campaigns. Skipping generation.")
            return

        generator = SampleDataGenerator(session)
        stats = generator.generate_all(
            n_influencers=20,
            n_products=30,
            n_campaigns=100,
        )
        logger.info(f"Sample data generated: {stats}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
