if not isinstance(imported, list):
                raise ValueError("ساختار فایل معتبر نیست.")

            existing_ids = {
                str(r["id"]) for r in records
            }

            new_records = []

            for item in imported:
                required = [
                    "id", "title", "question",
                    "kind", "status", "sources"
                ]

                if not isinstance(item, dict):
                    raise ValueError("رکورد نامعتبر است.")

                if not all(k in item for k in required):
                    raise ValueError("اطلاعات یک رکورد ناقص است.")

                record_id = str(uuid.UUID(str(item["id"])))

                if record_id in existing_ids:
                    continue

                new_record = {
                    "id": record_id,
                    "title": str(item["title"]),
                    "question": str(item["question"]),
                    "kind": str(item["kind"]),
                    "status": str(item["status"]),
                    "sources": str(item.get("sources", ""))
                }

                if item.get("created_at"):
                    new_record["created_at"] = item["created_at"]

                new_records.append(new_record)
                existing_ids.add(record_id)

            if new_records:
                db.table("research_records").insert(
                    new_records
                ).execute()

            st.success(
                f"{len(new_records)} رکورد بازیابی شد."
            )
            st.rerun()

        except Exception as error:
            st.error(f"خطا در بازیابی اطلاعات: {error}")

st.divider()

st.caption(
    "Beyond Cognition | Persistent Research Core | Version 0.2"
)
