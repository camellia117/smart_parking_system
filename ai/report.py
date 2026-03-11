from openai import OpenAI

client = OpenAI()

def generate_report(stats):

    prompt = f"""
    停车系统统计数据

    总收入:{stats['total_revenue']}
    平均停车时间:{stats['avg_parking_time']}

    请生成停车运营分析报告
    """

    res = client.chat.completions.create(

        model="gpt-4o-mini",

        messages=[{"role":"user","content":prompt}]

    )

    return res.choices[0].message.content