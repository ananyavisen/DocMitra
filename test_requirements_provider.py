from core.services.requirements_provider import RequirementsProvider


def main():
    provider = RequirementsProvider()

    # Test 1: Retrieve a checklist.
    checklist = provider.get_checklist("degree_first_year")

    print("\n=== DEGREE FIRST-YEAR CHECKLIST ===")
    print("Student type:", checklist["student_type"])

    for category, documents in checklist["checklist"].items():
        print(f"\n{category.upper()}")

        for document in documents:
            print(
                f"- {document['name']} | "
                f"Verification: {document['verification_status']} | "
                f"Verified for processing: "
                f"{document['verified_for_processing']}"
            )

    print("\nWarnings:", checklist["warnings"])

    # Test 2: Retrieve processing constraints.
    constraints = provider.get_processing_constraints()

    print("\n=== PROCESSING CONSTRAINTS ===")
    print("Count:", constraints["count"])
    print("Constraints:", constraints["processing_constraints"])
    print("Excluded documents:", len(constraints["excluded_documents"]))

    # The current knowledge base should not produce constraints
    # from older copies or unverified sources.
    assert constraints["count"] == 0, (
        "Unexpected processing constraints found. "
        "Review their verification statuses and JSON definitions."
    )

    print("\nTests passed.")


if __name__ == "__main__":
    main()