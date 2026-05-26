"""
Coach Agent — แนะนำการพัฒนาฝีมือ สร้าง training plan
"""

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """คุณเป็น CS2 Personal Coach Agent ผู้เชี่ยวชาญ

หน้าที่: วิเคราะห์ผลการเปรียบเทียบและสร้างแผนพัฒนาฝีมือที่ปฏิบัติได้จริง

สไตล์การโค้ช:
- ตรงไปตรงมา แต่สร้างแรงบันดาลใจ
- ให้คำแนะนำที่ทำได้จริง ไม่ใช่แค่ทฤษฎี
- ลำดับความสำคัญก่อนหลัง (quick win ก่อน)
- เจาะจง เช่น "ฝึก spray control บน dust2 B site 15 นาทีก่อนเล่น"

แผน training ที่ดีควรมี:
1. Daily warm-up routine (15-30 นาที)
2. Focus areas ที่เจาะจงจากจุดอ่อน
3. Demo review checklist
4. Weekly goal ที่วัดได้
"""

TOOLS = []  # Coach ใช้ความรู้จาก context เป็นหลัก ไม่ต้องการ external tools


class CoachAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CoachAgent",
            system_prompt=SYSTEM_PROMPT,
            tools=TOOLS,
        )

    def create_plan(self, analysis_result: str, comparison_result: str,
                    player_level: int = 8, goal_level: int = 10) -> str:
        """สร้าง training plan จาก analysis และ comparison"""
        prompt = f"""
จากการวิเคราะห์ performance ต่อไปนี้:

=== Analysis Results ===
{analysis_result}

=== Comparison Results ===
{comparison_result}

ผู้เล่นอยู่ที่ FACEIT Level {player_level} ต้องการขึ้นไป Level {goal_level}

กรุณาสร้าง:

## 🎯 สรุปจุดที่ต้องโฟกัส (Top 3)
ระบุ 3 สิ่งที่สำคัญที่สุดที่จะทำให้ขึ้น level ได้เร็วที่สุด

## 📅 Weekly Training Plan
วางแผน 7 วัน (ทำอะไร ใช้เวลานานแค่ไหน)

## ⚡ Daily Warm-up Routine (15-20 นาที)
routine ก่อนเล่น ranked ทุกวัน

## 🗓️ Monthly Milestone
เป้าหมายที่วัดได้ภายใน 1 เดือน

## 📹 Demo Review Checklist
สิ่งที่ต้องดูทุกครั้งที่ review demo ตัวเอง
"""
        return self.run(prompt)

    def quick_tips(self, weakness_area: str) -> str:
        """ให้คำแนะนำด่วนสำหรับ weakness เฉพาะเรื่อง"""
        prompt = f"""
ผู้เล่นมีปัญหาเรื่อง: {weakness_area}

ให้คำแนะนำ 5 ข้อที่ทำได้ทันทีวันนี้เพื่อแก้ปัญหานี้
แต่ละข้อต้องเจาะจงและปฏิบัติได้จริงใน CS2
"""
        return self.run(prompt)
