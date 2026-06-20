"""
Tortoise ORM 模型: Stock
"""
from tortoise import fields
from tortoise.models import Model


class Stock(Model):
    """股票列表。"""
    symbol = fields.CharField(max_length=20, pk=True)  # 主键，如 AAPL
    name = fields.CharField(max_length=100, null=True)  # 可选: 公司名
    enabled = fields.BooleanField(default=True)  # 是否启用（定时任务用）
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "stocks"
        ordering = ["symbol"]

    def __repr__(self):
        return f"<Stock {self.symbol}>"
