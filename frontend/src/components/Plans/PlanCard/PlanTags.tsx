import React from "react";
import Badge from "../../base/Badges/Badges";
import { tagList } from "./PlanCard";
interface PlanTagsProps {
  userTags: typeof tagList;
}

const PlansTags = ({ userTags }: PlanTagsProps) => {
  return (
    <>
      {!userTags.length ? (
        <Badge className="bg-[#E0E7FF] text-[#3730A3] text-[12px] px-2 py-0.5">
          <Badge.Content>+ Add Tag</Badge.Content>
        </Badge>
      ) : (
        <span className="flex">
          {userTags.length >= 3 ? (
            <span className="flex gap-2">
              {userTags.slice(0, 2).map((el) => (
                <span className="flex gap-2">
                  <Badge
                    className={
                      "text-[12px] px-2 py-0.5 bg-white text-black whitespace-nowrap"
                    }
                  >
                    <Badge.Dot style={{ color: el.hex }} />
                    <Badge.Content> {el.text}</Badge.Content>
                  </Badge>
                </span>
              ))}
              <span className="whitespace-nowrap">
                {" "}
                +{userTags.length} tags
              </span>
            </span>
          ) : (
            userTags.map((el) => (
              <Badge className={"text-[12px] px-2 py-0.5 bg-white text-black"}>
                <Badge.Dot style={{ color: el.hex }} />
                <Badge.Content> {el.text}</Badge.Content>
              </Badge>
            ))
          )}
        </span>
      )}
    </>
  );
};
export default PlansTags;
