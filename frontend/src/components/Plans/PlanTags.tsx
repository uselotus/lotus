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
        <Badge className="bg-[#E0E7FF] text-[#3730A3] text-[12px] px-[6px] py-2">
          <Badge.Content>+ Add Tag</Badge.Content>
        </Badge>
      ) : (
        <span className="flex">
          {tags.length >= 3 ? (
            <span className="flex gap-2">
              {tags.slice(0, 2).map((tag) => (
                <span className="flex gap-2" key={tag.tag_name}>
                  <Badge
                    className={`text-[12px] px-[5px] py-0.5 bg-white text-black whitespace-nowrap`}
                  >
                    <div className="flex gap-2 items-center">
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
              <span className="flex gap-2">
                <span className="flex gap-2" key={tag.tag_name}>
                  <Badge
                    className={`text-[12px] px-[5px] py-2 bg-white text-black whitespace-nowrap`}
                  >
                    <div className="flex gap-2 items-center">
                      <Badge.Dot fill={tag.tag_hex} />
                      <Badge.Content>{tag.tag_name}</Badge.Content>
                    </div>
                  </Badge>
                </span>
                <Badge className="bg-[#E0E7FF] text-[#3730A3] text-[12px] px-[6px] py-2 ml-2 whitespace-nowrap">
                  <Badge.Content>+ Add Tag</Badge.Content>
                </Badge>
              </span>
            ))
          )}
        </span>
      )}
    </>
  );
};
export default PlansTags;
