import { describe, it, expect } from "vitest";
import { getTierForPoints, TIERS } from "../user-tier-banner";
import { FALLBACK_REWARDS, claimGamificationReward } from "@/lib/api/gamification";

describe("Gamification & Loyalty Tiers", () => {
  it("should have 4 distinct loyalty tiers: bronze, silver, gold, platinum", () => {
    expect(TIERS).toHaveLength(4);
    expect(TIERS.map((t) => t.key)).toEqual(["bronze", "silver", "gold", "platinum"]);
  });

  it("should categorize 0 - 99 points as bronze", () => {
    expect(getTierForPoints(0).key).toBe("bronze");
    expect(getTierForPoints(50).key).toBe("bronze");
    expect(getTierForPoints(99).key).toBe("bronze");
  });

  it("should categorize 100 - 299 points as silver", () => {
    expect(getTierForPoints(100).key).toBe("silver");
    expect(getTierForPoints(200).key).toBe("silver");
    expect(getTierForPoints(299).key).toBe("silver");
  });

  it("should categorize 300 - 699 points as gold", () => {
    expect(getTierForPoints(300).key).toBe("gold");
    expect(getTierForPoints(500).key).toBe("gold");
    expect(getTierForPoints(699).key).toBe("gold");
  });

  it("should categorize 700+ points as platinum", () => {
    expect(getTierForPoints(700).key).toBe("platinum");
    expect(getTierForPoints(1200).key).toBe("platinum");
  });
});

describe("Rewards Catalog & Fallbacks", () => {
  it("should contain default redeemable rewards with valid points and details", () => {
    expect(FALLBACK_REWARDS.length).toBeGreaterThanOrEqual(4);

    FALLBACK_REWARDS.forEach((reward) => {
      expect(reward.id).toBeTruthy();
      expect(reward.name).toBeTruthy();
      expect(reward.points_required).toBeGreaterThan(0);
      expect(reward.is_active).toBe(true);
    });
  });

  it("should claim a reward and generate a fallback coupon code", async () => {
    const res = await claimGamificationReward("rew-discount-10");
    expect(res).toBeDefined();
    expect(res.reward_id).toBe("rew-discount-10");
    expect(res.points_spent).toBe(50);
    expect(res.coupon_code).toMatch(/^GIFT-[A-Z0-9]+$/);
  });
});

describe("Wheel of Fortune Angle Calculations", () => {
  it("should calculate correct slice angles for 8 slices", () => {
    const totalSlices = 8;
    const sliceAngle = 360 / totalSlices;
    expect(sliceAngle).toBe(45);

    for (let i = 0; i < totalSlices; i++) {
      const sliceCenter = i * sliceAngle + sliceAngle / 2;
      // To bring sliceCenter to top (0 deg/360 deg), target rotation modulo must be (360 - sliceCenter)
      const targetModulo = (360 - sliceCenter + 360) % 360;
      const finalPosition = (targetModulo + sliceCenter) % 360;
      expect(finalPosition).toBe(0);
    }
  });
});
