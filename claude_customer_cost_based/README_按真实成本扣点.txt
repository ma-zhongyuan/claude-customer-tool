这个版本已经改成：
【按 Anthropic 真实成本扣点】

逻辑：
1. 顾客提问
2. Claude 返回 usage（input_tokens / output_tokens）
3. 系统按价格换算美元成本
4. 再把美元成本换算成顾客点数

默认设置：
- CREDITS_PER_USD=10000
  表示 10000 点 = 1 美元
- BILLING_MULTIPLIER=1.0
  表示不加价，按真实成本扣点

如果你想赚钱，可以把：
- BILLING_MULTIPLIER=1.2  或  1.5

这样系统会自动在真实成本上乘一个倍数。

默认模型价格（适合 Sonnet 4.6）：
- MODEL_INPUT_PRICE_PER_MTOK=3.0
- MODEL_OUTPUT_PRICE_PER_MTOK=15.0

如果以后你换模型，只要改 .env 里的价格，不用改代码。
