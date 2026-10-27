from core.validation.document_validator import validate_pdf

file_path = r"C:\Users\anany\OneDrive\Desktop\me.pdf.jpg"

result = validate_pdf(file_path)

print(result.to_dict())

if result.valid:
    print("Document passed validation.")
else:
    print("Document failed validation.")

    for error in result.errors:
        print(f"- {error}")