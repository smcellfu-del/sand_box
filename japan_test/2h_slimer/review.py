import json
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

BASE_PATH = Path("sandbox/japan_test/2h_slimer/debug-4/_phoneme_dataset")

INPUT_FILE = BASE_PATH / "error_units.json"
REVIEW_FILE = BASE_PATH / "reviewed_error_units.json"

MATRIX_FILE = BASE_PATH / "matrix_candidates.json"
WORD_ERROR_FILE = BASE_PATH / "word_error_dataset.json"
GAP_FILE = BASE_PATH / "gap_pool.json"

# ============================================================
# REVIEW MODE
# ============================================================

# 目前只人工審核 MISS（SUB）：
# - 必須至少有 1 個 SUB
# - 不允許 INSERT
# - 不允許 DELETE
MISS_ONLY = True

CATEGORY_MAP = {
    "1": {
        "category": "SINGLE_SUB_HIGH",
        "keep_dataset": True,
        "use_for_matrix": True,
    },
    "2": {
        "category": "WORD_MULTI_SUB",
        "keep_dataset": True,
        "use_for_matrix": False,
    },
    "3": {
        "category": "PHRASE_ERROR",
        "keep_dataset": False,
        "use_for_matrix": False,
    },
    "4": {
        "category": "PREPROCESSING_ERROR",
        "keep_dataset": False,
        "use_for_matrix": False,
    },
    "5": {
        "category": "GAP_POOL",
        "keep_dataset": True,
        "use_for_matrix": False,
    },
    "6": {
        "category": "UNCERTAIN",
        "keep_dataset": True,
        "use_for_matrix": False,
    },
}


# ============================================================
# HELPERS
# ============================================================

def load_json(path, default):
    if not path.exists():
        return default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def make_key(item):
    return (
        f"{item.get('song', '')}"
        f"::{item.get('block_id', '')}"
        f"::{item.get('unit_id', '')}"
    )


def show_alignment(alignment):
    l = []
    w = []
    op = []

    for item in alignment:
        l.append(item["l"])
        w.append(item["w"])

        if item["op"] == "MATCH":
            op.append("│")
        elif item["op"] == "SUB":
            op.append("×")
        elif item["op"] == "INSERT":
            op.append("+")
        elif item["op"] == "DELETE":
            op.append("-")
        else:
            op.append("?")

    width = max(
        2,
        max((len(x) for x in l + w), default=1)
    )

    def row(name, values):
        print(
            f"{name:<8}: "
            + " ".join(
                f"{x:^{width}}"
                for x in values
            )
        )

    row("Lyrics", l)
    row("", op)
    row("ASR", w)


def is_miss_only_unit(item):
    """
    只保留純 MISS（Substitution）錯誤：
    - SUB > 0
    - INSERT == 0
    - DELETE == 0

    MATCH 可以存在，因為我們要保留錯誤單字的完整 phoneme structure。
    """
    counts = item.get("counts", {})

    sub_count = counts.get("SUB", 0)
    insert_count = counts.get("INSERT", 0)
    delete_count = counts.get("DELETE", 0)

    # 舊資料若沒有 counts，就從 alignment 重算。
    if not counts:
        sub_count = 0
        insert_count = 0
        delete_count = 0

        for pair in item.get("alignment", []):
            op = pair.get("op")

            if op == "SUB":
                sub_count += 1
            elif op == "INSERT":
                insert_count += 1
            elif op == "DELETE":
                delete_count += 1

    return (
        sub_count > 0
        and insert_count == 0
        and delete_count == 0
    )


def show_context_alignment(context_alignment):
    if not context_alignment:
        return

    l = []
    w = []
    op = []
    mark = []

    for item in context_alignment:
        l.append(
            item.get("l", "-")
        )
        w.append(
            item.get("w", "-")
        )

        this_op = item.get(
            "op",
            "?"
        )

        if this_op == "MATCH":
            op.append("│")
        elif this_op == "SUB":
            op.append("×")
        elif this_op == "INSERT":
            op.append("+")
        elif this_op == "DELETE":
            op.append("-")
        else:
            op.append("?")

        mark.append(
            "^"
            if item.get("is_error_unit")
            else " "
        )

    width = max(
        2,
        max(
            (
                len(str(x))
                for x in l + w
            ),
            default=1
        )
    )

    def row(name, values):
        print(
            f"{name:<8}: "
            + " ".join(
                f"{str(x):^{width}}"
                for x in values
            )
        )

    row("Lyrics", l)
    row("", op)
    row("ASR", w)
    row("UNIT", mark)


def show_item(item, index, total):
    print("\n" + "=" * 100)
    print(f"[{index}/{total}]")
    print(f"Song   : {item.get('song')}")
    print(f"Block  : {item.get('block_id')}")
    print(f"Unit   : {item.get('unit_id')}")
    print(f"Auto   : {item.get('type')}")
    print("-" * 100)

    print("L segment:", ", ".join(item.get("l_segments", [])))
    for line in item.get("l_line", []):
        print("  L:", line)

    print("W segment:", ", ".join(item.get("w_segments", [])))
    for line in item.get("w_line", []):
        print("  W:", line)

    print("-" * 100)
    print(
        "L sequence:",
        item.get("l_sequence", "")
    )
    print(
        "W sequence:",
        item.get("w_sequence", "")
    )
    print()

    show_alignment(
        item.get("alignment", [])
    )

    context_alignment = item.get(
        "context_alignment",
        []
    )

    if context_alignment:
        print("\nLocal context（^ = 目前這個 Error Unit）：")
        show_context_alignment(
            context_alignment
        )

    else:
        print(
            "\n[舊 Dataset 沒有 context_alignment；"
            "請先用 context 版 Dataset 程式重跑一次]"
        )

    print("\n分類：")
    print("  1 = SINGLE_SUB_HIGH     單一乾淨 substitution，可進 Matrix")
    print("  2 = WORD_MULTI_SUB      整個詞的 MISS，保留完整結構")
    print("  3 = PHRASE_ERROR        大片語辨識錯誤，不進 clean dataset")
    print("  4 = PREPROCESSING_ERROR Reading / Sudachi / 前處理問題")
    print("  6 = UNCERTAIN           目前不確定，先保留")
    print("  s = skip                這筆晚點再看")
    print("  q = quit                儲存後離開")


def export_outputs(reviewed):
    matrix = []
    word_errors = []
    gaps = []

    for item in reviewed:
        category = item.get("review", {}).get(
            "category"
        )

        if category == "SINGLE_SUB_HIGH":
            matrix.append(item)

        elif category == "WORD_MULTI_SUB":
            word_errors.append(item)

        elif category == "GAP_POOL":
            gaps.append(item)

    save_json(
        MATRIX_FILE,
        matrix
    )

    save_json(
        WORD_ERROR_FILE,
        word_errors
    )

    save_json(
        GAP_FILE,
        gaps
    )


# ============================================================
# MAIN
# ============================================================

def main():
    source = load_json(
        INPUT_FILE,
        []
    )

    if not source:
        print(
            f"找不到資料：{INPUT_FILE}"
        )
        return

    reviewed = load_json(
        REVIEW_FILE,
        []
    )

    reviewed_map = {
        make_key(item): item
        for item in reviewed
    }

    if MISS_ONLY:
        review_source = [
            item
            for item in source
            if is_miss_only_unit(item)
        ]
    else:
        review_source = source

    pending = [
        item
        for item in review_source
        if make_key(item) not in reviewed_map
    ]

    skipped_gap_count = (
        len(source) - len(review_source)
        if MISS_ONLY
        else 0
    )

    print(
        f"全部 Error Units : {len(source)}"
    )

    if MISS_ONLY:
        print(
            f"純 MISS Units    : {len(review_source)}"
        )
        print(
            f"Gap/Mixed 已略過 : {skipped_gap_count}"
        )

    reviewed_in_mode = sum(
        1
        for item in review_source
        if make_key(item) in reviewed_map
    )

    print(
        f"已審核           : {reviewed_in_mode}"
    )
    print(
        f"待審核           : {len(pending)}"
    )

    if not pending:
        export_outputs(
            list(reviewed_map.values())
        )
        print("全部已審核完成。")
        return

    total = len(pending)

    for i, item in enumerate(
        pending,
        1
    ):
        show_item(
            item,
            i,
            total
        )

        while True:
            choice = input(
                "\n選擇 > "
            ).strip().lower()

            if choice == "q":
                reviewed_list = list(
                    reviewed_map.values()
                )

                save_json(
                    REVIEW_FILE,
                    reviewed_list
                )

                export_outputs(
                    reviewed_list
                )

                print("\n已儲存進度。")
                return

            if choice == "s":
                break

            if choice not in {"1", "2", "3", "4", "6"}:
                print(
                    "目前 MISS-only 模式：請輸入 1、2、3、4、6、s 或 q"
                )
                continue

            note = input(
                "note（可直接 Enter）> "
            ).strip()

            reviewed_item = dict(
                item
            )

            review = dict(
                CATEGORY_MAP[choice]
            )

            review["note"] = note

            reviewed_item["review"] = review

            reviewed_map[
                make_key(item)
            ] = reviewed_item

            reviewed_list = list(
                reviewed_map.values()
            )

            # 每判斷一筆就寫檔，避免中途遺失。
            save_json(
                REVIEW_FILE,
                reviewed_list
            )

            export_outputs(
                reviewed_list
            )

            print(
                f"已標記：{review['category']}"
            )

            break

    reviewed_list = list(
        reviewed_map.values()
    )

    save_json(
        REVIEW_FILE,
        reviewed_list
    )

    export_outputs(
        reviewed_list
    )

    print("\n全部 pending 資料已跑完。")


if __name__ == "__main__":
    main()