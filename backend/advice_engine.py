CROP_RULES = {
    "Rice": {
        "ph": (5.5, 7.5),
        "moisture": (60, 90),
        "temperature": (20, 35),
        "reason": "Rice performs well under warm conditions with relatively high soil moisture."
    },
    "Wheat": {
        "ph": (6.0, 7.5),
        "moisture": (40, 70),
        "temperature": (15, 25),
        "reason": "Wheat is generally suited to moderately moist soil and cooler growing temperatures."
    },
    "Maize": {
        "ph": (5.8, 7.0),
        "moisture": (50, 80),
        "temperature": (18, 32),
        "reason": "Maize is suited to moderately moist soil and warm temperatures."
    },
    "Groundnut": {
        "ph": (5.5, 7.0),
        "moisture": (40, 70),
        "temperature": (20, 30),
        "reason": "Groundnut is suited to moderately moist, well-conditioned soil and warm temperatures."
    },
    "Millet": {
        "ph": (5.5, 7.5),
        "moisture": (30, 60),
        "temperature": (20, 35),
        "reason": "Millet can tolerate comparatively lower moisture conditions and warm temperatures."
    }
}


def _check_range(value, limits):
    return limits[0] <= value <= limits[1]


def recommend_crops(ph, moisture, temperature, nitrogen, cec, fertility):
    recommendations = []

    for crop, rule in CROP_RULES.items():
        checks = {
            "pH": _check_range(ph, rule["ph"]),
            "moisture": _check_range(moisture, rule["moisture"]),
            "temperature": _check_range(temperature, rule["temperature"])
        }

        matched = sum(checks.values())

        if matched == 3:
            suitability = "Suitable"
        elif matched == 2:
            suitability = "Moderately Suitable"
        else:
            suitability = "Less Suitable"

        failed = [name for name, ok in checks.items() if not ok]

        if failed:
            reason = (
                f"{rule['reason']} "
                f"The current {', '.join(failed)} condition(s) "
                f"are outside the defined suitability range."
            )
        else:
            reason = (
                f"{rule['reason']} "
                f"The current pH, moisture and temperature conditions "
                f"match the defined suitability ranges."
            )

        recommendations.append({
            "crop": crop,
            "suitability": suitability,
            "reason": reason,
            "matched_conditions": matched,
            "total_conditions": 3,
            "conditions": checks
        })

    priority = {
        "Suitable": 0,
        "Moderately Suitable": 1,
        "Less Suitable": 2
    }

    recommendations.sort(
        key=lambda x: (priority[x["suitability"]], -x["matched_conditions"])
    )

    return {
        "fertility": fertility,
        "summary": (
            "Crop suitability is determined using the predicted fertility "
            "condition together with soil and environmental parameters."
        ),
        "recommendations": recommendations
    }