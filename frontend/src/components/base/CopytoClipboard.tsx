// @ts-ignore
import React, { useEffect, useState, useRef } from "react";
import { CheckCircleOutlined, CopyOutlined } from "@ant-design/icons";
import "./CopytoClipboard.css";
import { Tooltip } from "antd";
// import Prism from "prismjs";

interface CopyTextProps {
  textToCopy: string;
  className?: string;
  showIcon?: boolean;
  onlyIcon?: boolean;
  language?: string;
}

const CopyText: React.FC<CopyTextProps> = ({
  textToCopy,
  className,
  showIcon,
  onlyIcon,
  language,
}) => {
  const [copySuccess, setCopySuccess] = useState(false);
  const codeRef = useRef(null);

  // useEffect(() => {
  //   if (codeRef.current) {
  //     Prism.highlightElement(codeRef.current);
  //   }
  // }, [textToCopy]);

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
      <div className="copyText" onClick={() => copyToClipBoard(textToCopy)}>
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
            <code
              ref={codeRef}
              className={`language-${language} text-to-copy font-menlo`}
            >
              {textToCopy}
            </code>
          )}
          {!!showIcon && <CopyOutlined />}
        </Tooltip>
      </div>
    </div>
  );
};

export default CopyText;
