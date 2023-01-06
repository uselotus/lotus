import React from "react";
import { PlanType } from "../../types/plan-type";
import Badge from "../base/Badges/Badges";

interface PlanTagsProps {
  tags: PlanType["tags"];
}

const PlansTags = ({ tags }: PlanTagsProps) => {
  return (
    <>
      {!tags.length ? (
        <Badge className="bg-[#E0E7FF] text-[#3730A3] text-[12px] px-2 py-0.5">
          <Badge.Content>+ Add Tag</Badge.Content>
        </Badge>
      ) : (
        <span className="flex">
          {tags.length >= 3 ? (
            <span className="flex gap-2">
              {tags.slice(0, 2).map((tag) => (
                <span className="flex gap-2">
                  <Badge
                    className={`text-[12px] px-2 py-0.5 bg-white text-black whitespace-nowrap`}
                  >
                    <div className="flex gap-2">
                      <Badge.Dot className={`text-${tag.tag_hex}`} />
                      <Badge.Content>{tag.tag_name}</Badge.Content>
                    </div>
                  </Badge>
                </span>
              ))}
              <span className="whitespace-nowrap"> +{tags.length} tags</span>
            </span>
          ) : (
            tags.map((tag) => (
              <Badge
                className={`text-[12px] px-2 py-0.5 bg-white text-black whitespace-nowrap`}
              >
                <span className="flex gap-2 items-center">
                  <Badge.Dot fill={tag.tag_hex} />
                  <Badge.Content>{tag.tag_name}</Badge.Content>
                </span>
              </Badge>
            ))
          )}
        </span>
      )}
    </>
  );
};
export default PlansTags;
