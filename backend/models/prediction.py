"""
Tortoise ORM 模型: Prediction, PredictionPoint
"""
from tortoise import fields
from tortoise.models import Model


class Prediction(Model):
    """预测主记录。"""
    id = fields.UUIDField(pk=True)
    symbol = fields.CharField(max_length=20)
    interval = fields.CharField(max_length=10, default="1d")
    hist_points = fields.IntField(default=252)
    pred_horizon = fields.IntField(default=10)
    n_predictions = fields.IntField(default=30)
    last_close = fields.DecimalField(max_digits=12, decimal_places=4, null=True)
    upside_prob = fields.DecimalField(max_digits=6, decimal_places=4, null=True)
    vol_amp_prob = fields.DecimalField(max_digits=6, decimal_places=4, null=True)
    chart_path = fields.CharField(max_length=500, null=True)
    status = fields.CharField(max_length=20, default="pending")  # pending/completed/failed
    error_message = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    # 反向关联
    points: fields.ReverseRelation["PredictionPoint"]

    class Meta:
        table = "predictions"
        ordering = ["-created_at"]

    def __repr__(self):
        return f"<Prediction {self.id} [{self.symbol}] {self.status}>"


class PredictionPoint(Model):
    """预测数据点（每一天一条记录）。"""
    id = fields.IntField(pk=True)
    prediction: fields.ForeignKeyRelation[Prediction] = fields.ForeignKeyField(
        "models.Prediction", related_name="points", on_delete=fields.CASCADE
    )
    date = fields.DateField()
    day_index = fields.IntField()  # 1-based: 第几个预测日
    mean_close = fields.DecimalField(max_digits=12, decimal_places=4)
    min_close = fields.DecimalField(max_digits=12, decimal_places=4)
    max_close = fields.DecimalField(max_digits=12, decimal_places=4)
    mean_volume = fields.DecimalField(max_digits=20, decimal_places=2)

    class Meta:
        table = "prediction_points"
        ordering = ["day_index"]
        unique_together = [("prediction_id", "day_index")]

    def __repr__(self):
        return f"<PredictionPoint day={self.day_index} close={self.mean_close}>"
