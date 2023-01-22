import { PlusOutlined } from "@ant-design/icons";
import type { InputRef } from "antd";
import { Input, Tag, Tooltip } from "antd";
// @ts-ignore
import React, { useEffect, useRef, useState, memo } from "react";
import Badge from "../base/Badges/Badges";

interface LinkExternalIdsProps {
  externalIds: string[];
  setExternalLinks?: (links: string[]) => void;
  createExternalLink?: (link) => void;
  deleteExternalLink?: (link) => void;
}

const LinksExternalIds: React.FC<LinkExternalIdsProps> = ({
  externalIds: tags,
  createExternalLink,
  deleteExternalLink,
  setExternalLinks,
}) => {
  const [inputVisible, setInputVisible] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const inputRef = useRef<InputRef>(null);
  const editInputRef = useRef<InputRef>(null);

  useEffect(() => {
    if (inputVisible) {
      inputRef.current?.focus();
    }
  }, [inputVisible]);

  useEffect(() => {
    editInputRef.current?.focus();
  }, [inputValue]);

  const handleClose = (removedTag: string) => {
    deleteExternalLink && deleteExternalLink(removedTag);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const handleInputConfirm = () => {
    if (inputValue && tags.indexOf(inputValue) === -1 && !setExternalLinks) {
      createExternalLink && createExternalLink(inputValue);
    } else if (
      inputValue &&
      tags.indexOf(inputValue) === -1 &&
      setExternalLinks
    ) {
      tags.push(inputValue);
      setExternalLinks(tags);
    }
    setInputVisible(false);
    setInputValue("");
  };

  return (
    <>
      {tags.map((tag) => {
        const isLongTag = tag.length > 20;
        const tagElem = (
          <Tag
            className="edit-tag"
            key={tag}
            closable
            onClose={() => handleClose(tag)}
          >
            <span>{isLongTag ? `${tag.slice(0, 20)}...` : tag}</span>
          </Tag>
        );
        return isLongTag ? (
          <Tooltip title={tag} key={tag}>
            {tagElem}
          </Tooltip>
        ) : (
          tagElem
        );
      })}
      {inputVisible && (
        <Input
          ref={inputRef}
          type="text"
          size="small"
          className="tag-input"
          value={inputValue}
          onChange={handleInputChange}
          onBlur={handleInputConfirm}
          onPressEnter={handleInputConfirm}
        />
      )}
      {!inputVisible && (
        <Badge
          onClick={() => setInputVisible(true)}
          className={
            setExternalLinks
              ? "bg-[#E0E7FF] text-[#3730A3] cursor-pointer w-1/2"
              : "bg-[#E0E7FF] text-[#3730A3] cursor-pointer"
          }
        >
          <Badge.Content>Link External IDs</Badge.Content>
        </Badge>
      )}
    </>
  );
};
const LinkExternalIds = memo(LinksExternalIds);
export default LinkExternalIds;
