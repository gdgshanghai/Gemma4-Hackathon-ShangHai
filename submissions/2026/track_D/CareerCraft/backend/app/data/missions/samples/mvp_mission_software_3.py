"""CouponService — legacy issuance logic in dire need of refactoring.

Smells: god method, magic numbers, type-flag branching, mixed I/O + business
logic, hard-coded SMS templates. Your task is to (1) split issueCoupon into
cohesive smaller methods and (2) introduce a Coupon polymorphic hierarchy
(DiscountCoupon, FullReductionCoupon, ...) that closes the door on the type
switch.
"""


class CouponService:
    def __init__(self, db, sms_client):
        self._db = db
        self._sms = sms_client

    def issueCoupon(self, user_id, coupon_type, amount, threshold=None,
                    expires_in_days=7, send_sms=True, source=None):
        # validation
        if coupon_type not in ("discount", "full_reduction", "free_shipping"):
            raise ValueError("unknown coupon type")
        if coupon_type == "discount" and not (0 < amount < 1):
            raise ValueError("discount amount must be (0,1)")
        if coupon_type == "full_reduction" and (threshold is None or amount >= threshold):
            raise ValueError("invalid full_reduction parameters")

        # eligibility
        user = self._db.fetch_user(user_id)
        if user is None or user.is_blocked:
            return None
        recent = self._db.count_user_coupons_today(user_id)
        if recent >= 3:
            return None

        # construct payload (branchy)
        if coupon_type == "discount":
            label = f"{int(amount * 100)}%off"
            payload = {"type": "discount", "amount": amount, "label": label}
        elif coupon_type == "full_reduction":
            label = f"满{threshold}减{amount}"
            payload = {"type": "full_reduction", "amount": amount,
                       "threshold": threshold, "label": label}
        else:
            label = "包邮券"
            payload = {"type": "free_shipping", "label": label}

        # persist
        coupon_id = self._db.insert_coupon(
            user_id=user_id, payload=payload,
            expires_in_days=expires_in_days, source=source,
        )

        # notify
        if send_sms and user.phone:
            if coupon_type == "discount":
                self._sms.send(user.phone, f"您获得了 {label}，{expires_in_days} 天内有效")
            elif coupon_type == "full_reduction":
                self._sms.send(user.phone, f"您获得了 {label}，{expires_in_days} 天内有效")
            else:
                self._sms.send(user.phone, f"您获得了 {label}")

        return coupon_id
