from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
LANDING = ROOT / "landing_zone"

SEED = 42
RUN_DATE = datetime.now().strftime("%Y%m%d")

VOLUMES = {
    "payers":        100,
    "facilities":    500,
    "providers":   5_000,
    "patients":   50_000,
    "claims":     50_000,
    "labs":       50_000,
    "prescriptions": 50_000,
    "financials": 50_000,
}

ICD10_CODES = [
    ("E11.9",  "Type 2 diabetes mellitus without complications"),
    ("I10",    "Essential (primary) hypertension"),
    ("J45.909","Unspecified asthma, uncomplicated"),
    ("M54.5",  "Low back pain"),
    ("F41.1",  "Generalized anxiety disorder"),
    ("K21.0",  "GERD with esophagitis"),
    ("E78.5",  "Hyperlipidemia, unspecified"),
    ("N39.0",  "Urinary tract infection"),
    ("J06.9",  "Acute upper respiratory infection"),
    ("Z00.00", "General adult medical exam without abnormal findings"),
    ("I25.10", "Atherosclerotic heart disease, unspecified"),
    ("F32.9",  "Major depressive disorder, single episode"),
    ("J18.9",  "Pneumonia, unspecified organism"),
    ("K92.1",  "Melena"),
    ("R51",    "Headache"),
]

CPT_CODES = [
    ("99213", "Office visit, established patient, low-moderate complexity", 150.00),
    ("99214", "Office visit, established patient, moderate-high complexity", 250.00),
    ("99215", "Office visit, established patient, high complexity",          350.00),
    ("99203", "Office visit, new patient, moderate complexity",              200.00),
    ("99204", "Office visit, new patient, moderate-high complexity",         300.00),
    ("93000", "Electrocardiogram (ECG/EKG)",                                  75.00),
    ("80053", "Comprehensive metabolic panel",                                85.00),
    ("85025", "Complete blood count (CBC)",                                   60.00),
    ("71046", "Chest X-ray, 2 views",                                        120.00),
    ("99285", "Emergency department visit, high complexity",                 650.00),
]

LAB_TESTS = [
    ("Hemoglobin",        "718-7",   "g/dL",  12.0, 17.5, 7.0, 20.0),
    ("Hematocrit",        "4544-3",  "%",     37.0, 52.0, 20.0, 60.0),
    ("Glucose",           "2345-7",  "mg/dL", 70.0, 100.0, 40.0, 500.0),
    ("Creatinine",        "2160-0",  "mg/dL",  0.6,   1.2,  0.3,   8.0),
    ("Total Cholesterol", "2093-3",  "mg/dL", 0.0,  200.0, 80.0, 400.0),
    ("LDL Cholesterol",   "13457-7", "mg/dL", 0.0,  100.0, 20.0, 250.0),
    ("Triglycerides",     "2571-8",  "mg/dL", 0.0,  150.0, 30.0, 500.0),
    ("HbA1c",             "4548-4",  "%",      4.0,    5.6,  3.5,  15.0),
    ("Troponin I",        "6598-7",  "ng/mL",  0.0,   0.04,  0.0,   5.0),
    ("CRP",               "1988-5",  "mg/L",   0.0,   3.0,   0.0, 200.0),
]

DRUGS = [
    ("Metformin",     "00093-1048-01", "500mg",  "Twice daily"),
    ("Lisinopril",    "00093-1046-01", "10mg",   "Once daily"),
    ("Atorvastatin",  "00069-0155-30", "20mg",   "Once daily at bedtime"),
    ("Amlodipine",    "00069-1540-30", "5mg",    "Once daily"),
    ("Omeprazole",    "00093-7366-56", "20mg",   "Once daily before meal"),
    ("Levothyroxine", "00074-4137-13", "50mcg",  "Once daily"),
    ("Sertraline",    "00049-4900-66", "50mg",   "Once daily"),
    ("Albuterol",     "00173-0682-20", "90mcg",  "Every 4-6 hours as needed"),
    ("Gabapentin",    "00093-0636-56", "300mg",  "Three times daily"),
    ("Amoxicillin",   "00093-4159-01", "500mg",  "Every 8 hours"),
]

SPECIALTIES = [
    "Cardiology", "Internal Medicine", "Family Medicine", "Pediatrics",
    "Oncology", "Orthopedics", "Neurology", "Psychiatry", "Radiology",
    "Emergency Medicine", "Obstetrics & Gynecology", "Dermatology",
    "Gastroenterology", "Pulmonology", "Endocrinology", "Nephrology",
    "Infectious Disease", "Rheumatology", "Urology", "Ophthalmology",
]

PAYER_NAMES = [
    "BlueCross BlueShield", "Aetna Health", "United Healthcare", "Cigna",
    "Humana", "Kaiser Permanente", "Centene", "Molina Healthcare",
    "WellCare Health", "CVS Health", "Anthem", "Independence Health",
    "HCSC", "Highmark", "Health Net", "Tufts Health Plan",
    "CareFirst", "Premera Blue Cross", "Regence", "BCBS of Tennessee",
]

HOSPITAL_NAMES = [
    "General Hospital", "Medical Center", "Regional Hospital",
    "Community Medical Center", "Memorial Hospital", "University Hospital",
    "St. Mary's Hospital", "Children's Hospital", "County Hospital",
    "Specialty Clinic", "Urgent Care Center", "Family Health Clinic",
    "Diagnostic Laboratory", "Outpatient Surgery Center",
]

DEPARTMENTS = [
    "Cardiology", "Oncology", "Emergency", "Radiology", "Pharmacy",
    "Laboratory", "Surgery", "Pediatrics", "ICU", "Outpatient",
    "Administration", "Billing", "IT", "Nursing", "Physical Therapy",
]

GL_ACCOUNTS = {
    "Revenue":       ["4000-Patient Revenue", "4100-Insurance Reimbursement", "4200-Grant Income"],
    "Expense":       ["5000-Salaries", "5100-Medical Supplies", "5200-Equipment", "5300-Utilities"],
    "Reimbursement": ["6000-Medicare Reimbursement", "6100-Medicaid Reimbursement", "6200-Commercial Reimb"],
    "Write-off":     ["7000-Bad Debt Write-off", "7100-Contractual Adjustment", "7200-Charity Care"],
}

