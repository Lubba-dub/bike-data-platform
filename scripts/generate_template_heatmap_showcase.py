﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿from __future__ import annotations

import json

from build_bike_template_engine_suite import build_suite


def main() -> None:
    summary = build_suite(
        visual_subdir="template_heatmap_showcase",
        write_legacy_showcase_summary=True,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
