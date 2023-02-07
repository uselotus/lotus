import React, { useState } from "react";
import { Input } from "antd";
import { CheckCircleOutlined } from "@ant-design/icons";
import ChevronDown from "../components/base/ChevronDown";
import DropdownComponent from "../components/base/Dropdown/Dropdown";
import { PlanType } from "../types/plan-type";
import Badge from "../components/base/Badges/Badges";
import PlansTags from "../components/Plans/PlanTags";
interface ViewPlansFilterProps {
  onChangeHandler: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onSelectHandler: (tag: tag, remove: boolean) => void;
  onFocusHandler: (focus: boolean) => void;
  value: string;
  tags: PlanType["tags"];
}
type T = PlanType["tags"][0];

interface tag extends T {
  from?: boolean;
}

const ViewPlansFilter = ({
  value,
  onChangeHandler,
  onSelectHandler,
  onFocusHandler,
  tags,
}: ViewPlansFilterProps) => {
  const [internalTags, setInternalTags] = useState<tag[]>([]);
  return (
    <div className="flex items-center gap-8 mb-10">
      <Input
        onFocus={() => onFocusHandler(true)}
        placeholder="Search plans..."
        className="!w-1/4 !bg-[#f8f8f8] border !border-[#f8f8f8]"
        value={value}
        onChange={onChangeHandler}
      />
      <DropdownComponent>
        <DropdownComponent.Trigger>
          {tags.length && tags && internalTags.length ? (
            <div className="flex gap-8 px-4 py-6 items-center border border-[#f8f8f8] bg-[#f8f8f8]">
              <PlansTags tags={internalTags} />
              <ChevronDown />
            </div>
          ) : (
            <button
              type="button"
              className="relative w-full px-4 py-6 flex items-center gap-8  cursor-default  bg-[#f8f8f8] rounded-md border border-[#f8f8f8]    text-left shadow-sm  focus:outline-none  sm:text-sm"
              aria-haspopup="listbox"
              aria-expanded="true"
              aria-labelledby="listbox-label"
            >
              <span className="block truncate">Tags</span>
              <ChevronDown />
            </button>
          )}
        </DropdownComponent.Trigger>
        <DropdownComponent.Container>
          {tags &&
            tags.map((tag: tag, index) => (
              <DropdownComponent.MenuItem
                onSelect={() => {
                  onFocusHandler(false);
                  if (tag.from) {
                    tag.from = false;
                    setInternalTags((prevTags) =>
                      prevTags.filter((t) => t.tag_name !== tag.tag_name)
                    );
                    onSelectHandler(tag, true);
                  } else {
                    tag.from = true;
                    setInternalTags((prevTags) => prevTags.concat(tag));
                    onSelectHandler(tag, false);
                  }
                }}
              >
                <span
                  key={index}
                  className="flex gap-2 items-center justify-between"
                >
                  <span className="flex gap-2 items-center">
                    <Badge.Dot fill={tag.tag_hex} />
                    <span className="text-black">{tag.tag_name}</span>
                  </span>
                  {tag.from && <CheckCircleOutlined className="!text-gold" />}
                </span>
              </DropdownComponent.MenuItem>
            ))}
        </DropdownComponent.Container>
      </DropdownComponent>
    </div>
  );
};
export default ViewPlansFilter;
