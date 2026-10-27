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
    file = serializers.FileField()
    doc_id = serializers.CharField(max_length=100)

    min_size_kb = serializers.IntegerField(
        min_value=1,
        required=False,
        default=1,
    )
    max_size_kb = serializers.IntegerField(
        min_value=1,
        max_value=10240,
        required=False,
        default=200,
    )

    width = serializers.IntegerField(
        min_value=1,
        max_value=5000,
        required=False,
    )
    height = serializers.IntegerField(
        min_value=1,
        max_value=5000,
        required=False,
    )

    def validate_file(self, uploaded_file):
        if uploaded_file.size == 0:
            raise serializers.ValidationError(
                "The uploaded file is empty."
            )

        if uploaded_file.size > 10 * 1024 * 1024:
            raise serializers.ValidationError(
                "File size must not exceed 10 MB."
            )

        return uploaded_file

    def validate_doc_id(self, value):
        from core.services.requirements_provider import RequirementsProvider

        provider = RequirementsProvider()

        if value not in provider.documents:
            raise serializers.ValidationError(
                "Unknown document ID."
            )

        return value

    def validate(self, attrs):
        if attrs["min_size_kb"] > attrs["max_size_kb"]:
            raise serializers.ValidationError(
                "min_size_kb cannot exceed max_size_kb."
            )

        if ("width" in attrs) != ("height" in attrs):
            raise serializers.ValidationError(
                "Provide both width and height for image processing."
            )

        if attrs["doc_id"] in {"passport_photo", "signature"}:
            if "width" not in attrs or "height" not in attrs:
                raise serializers.ValidationError({
                    "width": (
                        "Provide configured image dimensions for "
                        "passport photos and signatures."
                    ),
                    "height": (
                        "Provide configured image dimensions for "
                        "passport photos and signatures."
                    ),
                })

            if "max_size_kb" not in self.initial_data:
                raise serializers.ValidationError({
                    "max_size_kb": (
                        "Provide the applicable image-size limit."
                    )
                })

        return attrs