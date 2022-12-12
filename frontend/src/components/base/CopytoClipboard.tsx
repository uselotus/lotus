// @ts-ignore
import React, { useState } from "react";
import { CopyOutlined } from "@ant-design/icons";
import "./CopytoClipboard.css";
import { Tag } from "antd";

interface CopyTextProps {
  textToCopy: string;
}

const CopyText: React.FC<CopyTextProps> = ({ textToCopy }) => {
  const [copySuccess, setCopySuccess] = useState(false);

  const copyToClipBoard = async (copyMe) => {
    try {
      await navigator.clipboard.writeText(copyMe);
      setCopySuccess(true);
      setInterval(() => {
        setCopySuccess(false);
      }, 3000);
    } catch (err) {
      setCopySuccess(false);
    }
  };

  return (
    <div className="flex">
      <div className="copyText" onClick={() => copyToClipBoard(textToCopy)}>
        <span className="text-to-copy">{textToCopy}</span>
        <CopyOutlined />
      </div>
      {!!copySuccess && (
        <Tag className="copiedTag" color="green">
          Copied
        </Tag>
      )}
    </div>
  );
};

export default CopyText;
