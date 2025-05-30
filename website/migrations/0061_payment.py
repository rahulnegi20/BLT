# Generated by Django 3.0.8 on 2020-08-19 08:44

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("website", "0060_wallet_account_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                (
                    "id",
                    models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("value", models.DecimalField(decimal_places=2, max_digits=6)),
                ("active", models.BooleanField(default=True)),
                (
                    "wallet",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="website.Wallet"),
                ),
            ],
        ),
    ]
