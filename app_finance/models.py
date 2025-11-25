from decimal import Decimal
from django.db import models
from django.db.models import Sum

class Account(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('CASH', 'เงินสด'),
        ('BANK', 'บัญชีธนาคาร'),
        ('CREDIT', 'บัตรเครดิต'),
        ('LOAN', 'เงินกู้'),
        ('WALLET', 'E-Wallet'),
    ]
    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="สำหรับบัตรเครดิต/วงเงินกู้ ถ้ามี"
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="ดอกเบี้ยต่อปี (%) เช่น 16 สำหรับ 16%",
    )
    min_payment_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="เปอร์เซ็นต์ขั้นต่ำที่ต้องจ่ายจากยอดคงค้าง เช่น 5 สำหรับ 5%",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()})"

    @property
    def current_balance(self):
        total_in = self.transactions.filter(direction='IN').aggregate(
            s=Sum('amount')
        )['s'] or Decimal('0')
        total_out = self.transactions.filter(direction='OUT').aggregate(
            s=Sum('amount')
        )['s'] or Decimal('0')
        opening = self.opening_balance or Decimal('0')
        return opening + total_in - total_out


class Category(models.Model):

    KIND_CHOICES = [
        ('INCOME', 'รายรับ'),
        ('EXPENSE', 'รายจ่าย'),
    ]
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)

    is_debt_related = models.BooleanField(
        default=False,
        help_text="ติ๊กถ้าเป็นรายการเกี่ยวกับหนี้ เช่น ผ่อนหนี้, จ่ายบัตรเครดิต"
    )

    monthly_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="งบต่อเดือนสำหรับหมวดนี้ (ถ้าไม่ตั้งงบให้เว้นว่าง)"
    )

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"
    
class Tag(models.Model):
    """ป้ายกำกับ (เช่น เที่ยว, ครอบครัว, งาน) ให้แต่ละรายการ"""
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        help_text="ใส่สีแบบ #RRGGBB ถ้าอยากกำหนดสีเฉพาะ (ยังไม่บังคับใช้ก็ได้)"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
    
class TransactionTemplate(models.Model):
    """Template สำหรับรายการด่วน เช่น 'กาแฟ', 'BTS ไปทำงาน' ฯลฯ"""
    name = models.CharField(
        max_length=100,
        help_text="ชื่อ template เช่น กาแฟ, BTS ไปทำงาน"
    )
    direction = models.CharField(
        max_length=3,
        choices=[("IN", "รายรับ"), ("OUT", "รายจ่าย")],
        default="OUT",
    )
    default_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="จำนวนเงินเริ่มต้น (เปลี่ยนได้ตอนบันทึก)"
    )
    account = models.ForeignKey(
        "Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="บัญชีเริ่มต้น (เลือกใหม่ได้ตอนบันทึก)",
    )
    category = models.ForeignKey(
        "Category",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="หมวดเริ่มต้น",
    )
    note = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="โน้ตเริ่มต้น เช่น ร้านประจำ, เส้นทาง ฯลฯ",
    )
    tags = models.ManyToManyField(
        "Tag",
        blank=True,
        help_text="Tag เริ่มต้น เช่น เที่ยว, กาแฟ, เดินทาง",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name    
    
class Goal(models.Model):

    GOAL_DIRECTION_CHOICES = [
        ('IN', 'เงินเข้า'),
        ('OUT', 'เงินออก'),
    ]
    name = models.CharField(max_length=100)

    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="บัญชีที่เกี่ยวข้องกับเป้าหมายนี้ (ถ้ามี)"
    )

    target_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="จำนวนเงินเป้าหมาย เช่น 100000"
    )

    target_date = models.DateField(
        null=True,
        blank=True,
        help_text="อยากให้ถึงเป้าภายในวันไหน (ถ้าไม่กำหนดให้เว้นว่าง)"
    )

    direction = models.CharField(
        max_length=3,
        choices=GOAL_DIRECTION_CHOICES,
        default="IN",
        help_text="นับยอดจากรายการแบบไหนเป็นการเดินหน้าเป้าหมาย (ส่วนใหญ่ใช้ เงินเข้า)"
    )

    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Transaction(models.Model):

    DIRECTION_CHOICES = [
        ('IN', 'เงินเข้า'),
        ('OUT', 'เงินออก'),
    ]

    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    goal = models.ForeignKey(
        Goal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        help_text="ถ้ารายการนี้เกี่ยวข้องกับเป้าหมายเก็บเงิน ให้เลือก"
    )

    proof_file = models.FileField(
        upload_to="receipts/",
        null=True,
        blank=True,
        help_text="อัปโหลดรูปใบเสร็จหรือไฟล์หลักฐาน (ถ้ามี)",
    )

    tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name="transactions",
        help_text="เลือก tag ได้หลายอัน เช่น เที่ยว, ครอบครัว, งาน",
    )

    date = models.DateField()
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    is_estimate = models.BooleanField(
        default=False,
        help_text="ติ๊กถ้าเป็นรายการประเมิน/วางแผน ยังไม่ได้เกิดขึ้นจริง"
    )
    is_paid = models.BooleanField(
        default=True,
        help_text="ใช้คู่กับ is_estimate ถ้าเป็นประมาณการแล้วจ่ายจริงแล้ว"
    )

    note = models.TextField(blank=True, null=True)

    # 👇 ใหม่: เอาไว้ผูกว่ามาจาก recurring ตัวไหน (ถ้ามี)
    source_recurring = models.ForeignKey(
        'RecurringTransaction',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='generated_transactions'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        prefix = "ประมาณการ" if self.is_estimate else "จริง"
        return f"[{prefix}] {self.date} {self.get_direction_display()} {self.amount} ({self.account})"


class RecurringTransaction(models.Model):
    """
    รายการประจำ เช่น ค่าเช่า, ผ่อนหนี้, เน็ต, เงินเดือน ฯลฯ
    """
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    direction = models.CharField(
        max_length=3,
        choices=Transaction.DIRECTION_CHOICES
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    day_of_month = models.PositiveSmallIntegerField(
        help_text="วันที่ในเดือน (1-31) พระเอกใช้สร้างรายการของเดือนนั้น"
    )
    name = models.CharField(
        max_length=100,
        blank=True,
        help_text="คำอธิบายสั้น ๆ เช่น ค่าเช่าห้อง, ผ่อนรถ"
    )

    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True, help_text="เริ่มนับจากวันไหน (ถ้าไม่กรอกใช้ได้ทันที)")
    end_date = models.DateField(null=True, blank=True, help_text="สิ้นสุดวันไหน (ถ้าไม่กรอกให้ใช้ไปเรื่อย ๆ)")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        direction = "รับ" if self.direction == "IN" else "จ่าย"
        return f"[ประจำ] ทุกวันที่ {self.day_of_month} {direction} {self.amount} ({self.account})"
    
class CategoryBudget(models.Model):
    """
    งบประมาณรายจ่ายต่อหมวด ต่อเดือน/ปี
    ใช้เพื่อเทียบกับรายจ่ายจริงในแต่ละหมวด
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="budgets",
    )
    year = models.IntegerField()
    month = models.IntegerField(help_text="1-12")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="จำนวนเงินงบประมาณสำหรับเดือนนั้น",
    )
    note = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("category", "year", "month")
        ordering = ["-year", "-month", "category__name"]

    def __str__(self):
        return f"{self.category.name} {self.month:02d}/{self.year} - {self.amount}"

    @property
    def amount_display(self) -> Decimal:
        return self.amount or Decimal("0")

