import React, { useState } from "react";
import { CheckCircleOutlined, CopyOutlined } from "@ant-design/icons";
import "./CopytoClipboard.css";
import { Tooltip } from "antd";

interface CopyTextProps {
  textToCopy: string;
  className?: string;
  showIcon?: boolean;
  onlyIcon?: boolean;
}

const CopyText: React.FC<CopyTextProps> = ({
  textToCopy,
  className,
  showIcon,
  onlyIcon,
}) => {
  const [copySuccess, setCopySuccess] = useState(false);

  const copyToClipBoard = async (copyMe) => {
    try {
      await navigator.clipboard.writeText(copyMe);
      setCopySuccess(true);
      setTimeout(() => {
        setCopySuccess(false);
      }, 3000);
    } catch (err) {
      setCopySuccess(false);
    }
  };

  return (
    <div className={`${className} flex`}>
      <div
        aria-hidden
        className="copyText"
        onClick={() => copyToClipBoard(textToCopy)}
      >
        <Tooltip
          placement="right"
          title={
            copySuccess ? (
              <div className="copiedTag">
                <CheckCircleOutlined className="checkedIcon" /> Copied
              </div>
            ) : (
              <div>
                Click to Copy <CopyOutlined />
              </div>
            )
          }
        >
          {!onlyIcon && (
            <span className="text-to-copy font-menlo">{textToCopy}</span>
          )}
          {!!showIcon && <CopyOutlined />}
        </Tooltip>
      </div>
    </div>
  );
};

export default CopyText;
