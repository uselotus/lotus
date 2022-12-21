import { PlusOutlined } from "@ant-design/icons";
import type { InputRef } from "antd";
import { Input, Tag, Tooltip } from "antd";
// @ts-ignore
import React, { useEffect, useRef, useState, memo } from "react";

interface LinkExternalIdsProps {
  externalIds: string[];
  setExternalLinks?: (links: string[]) => void;
  createExternalLink?: (link) => void;
  deleteExternalLink?: (link) => void;
}

const LinksExternalIds: React.FC<LinkExternalIdsProps> = ({
  externalIds: tags,
  setExternalLinks,
  createExternalLink,
  deleteExternalLink,
}) => {
  const [inputVisible, setInputVisible] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const inputRef = useRef<InputRef>(null);
  const editInputRef = useRef<InputRef>(null);
  console.log(tags);
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
    if (inputValue && tags.indexOf(inputValue) === -1) {
      createExternalLink && createExternalLink(inputValue);
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
        <Tag className="site-tag-plus" onClick={() => setInputVisible(true)}>
          <PlusOutlined /> Link External IDs
        </Tag>
      )}
    </>
  );
};
const LinkExternalIds = memo(LinksExternalIds);
export default LinkExternalIds;
