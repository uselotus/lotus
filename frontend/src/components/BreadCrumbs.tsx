import clsx from "clsx";
import { RightOutlined } from "@ant-design/icons";
import React from "react";

interface BreadCrumbItemProps {
  label: string;
  onClick?: () => void;
  isActive: boolean;
}

const BreadCrumbItem = ({ label, onClick, isActive }: BreadCrumbItemProps) => (
  // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
  <div
    className={clsx(["inline-flex items-center justify-center"])}
    onClick={onClick}
    style={{
      color: isActive ? "#C3986B" : undefined,
    }}
  >
    {label}
  </div>
);

interface Props {
  items: string[];
  onItemClick?: (idx: number) => void;
  activeItem: number;
}

const BreadCrumbs = ({ items, activeItem, onItemClick }: Props) => (
  <div
    className={clsx([
      "inline-flex items-center justify-start",
      "cursor-pointer",
      "text-xs",
      "bg-gray-50",
      "p-4",
    ])}
  >
    {React.Children.toArray(
      items.map((item, index) => (
        <>
          <BreadCrumbItem
            label={item}
            onClick={() => onItemClick?.(index)}
            isActive={index <= activeItem}
          />
          {index < items.length - 1 && (
            <div className="px-4">
              <RightOutlined className="text-xs" />
            </div>
          )}
        </>
      ))
    )}
  </div>
);

export default BreadCrumbs;
