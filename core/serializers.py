from rest_framework import serializers


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, uploaded_file):
        allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg"}
        from pathlib import Path

        extension = Path(uploaded_file.name).suffix.lower()

        if extension not in allowed_extensions:
            raise serializers.ValidationError(
                "Only PDF, PNG, JPG and JPEG files are allowed."
            )
        if uploaded_file.size == 0:
            raise serializers.ValidationError("The uploaded file is empty.")

        if uploaded_file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "File size must not exceed 10 MB."
            )

        return uploaded_file

class ImageProcessSerializer(serializers.Serializer):
    file = serializers.ImageField()
    width = serializers.IntegerField(min_value=1, max_value=5000)
    height = serializers.IntegerField(min_value=1, max_value=5000)
    max_size_kb = serializers.IntegerField(min_value=1, max_value=10240)


class PDFProcessSerializer(serializers.Serializer):
    file = serializers.FileField()
    max_size_kb = serializers.IntegerField(
        min_value=1,
        max_value=10240,
        required=False
    )

    def validate_file(self, uploaded_file):
        from pathlib import Path

        extension = Path(uploaded_file.name).suffix.lower()

        if extension != ".pdf":
            raise serializers.ValidationError(
                "Only PDF files are allowed."
            )

        if uploaded_file.size == 0:
            raise serializers.ValidationError(
                "The uploaded PDF is empty."
            )

        if uploaded_file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "PDF size must not exceed 10 MB."
            )

        return uploaded_file



class DocumentProcessSerializer(serializers.Serializer):
    file = serializers.ImageField()
    doc_id = serializers.CharField(max_length=100)
    min_size_kb = serializers.IntegerField(min_value=1, required=False, default=1)
    max_size_kb = serializers.IntegerField(min_value=1, max_value=10240, required=False, default=200)

    def validate_file(self, uploaded_file):
        if uploaded_file.size == 0:
            raise serializers.ValidationError("The uploaded image is empty.")

        if uploaded_file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "File size must not exceed 10 MB."
            )

        return uploaded_file

    def validate_doc_id(self, value):
        from core.services.requirements_provider import get_document_by_id

        document = get_document_by_id(value)

        if not document:
            raise serializers.ValidationError("Unknown document ID.")

        if value in {"passport_photo", "signature"}:
            raise serializers.ValidationError(
                "Passport photos and signatures must use their own processing workflow."
            )

        return value

    def validate(self, attrs):
        if attrs["min_size_kb"] > attrs["max_size_kb"]:
            raise serializers.ValidationError(
                "min_size_kb cannot exceed max_size_kb."
            )
        return attrs
