import React from "react";
import { CheckCircleOutlined } from "@ant-design/icons";
import useGlobalStore from "../../stores/useGlobalstore";
import Badge from "../base/Badges/Badges";
interface SlideOverCardProps {}

const SlideOverCard: React.FC<SlideOverCardProps> = () => {
  const { linked_organizations } = useGlobalStore((state) => state.org);
  return (
    <>
      {linked_organizations?.map((org) => (
        <div
          className={
            org.current
              ? "bg-[#C3986B1A] p-8 flex cursor-pointer"
              : "bg-gold-100 p-8 flex cursor-pointer"
          }
        >
          <div className="flex gap-2 items-center">
            <Badge.Dot
              fill={org.organization_type !== "production" ? "#60A5FA" : ""}
            />
            <span
              className={
                org.organization_type !== "production"
                  ? " text-blue-800"
                  : "text-emerald-800"
              }
            >
              {org.organization_name} Environment
            </span>
          </div>
          <div className="ml-auto">
            <CheckCircleOutlined className="!text-gold" />
          </div>
        </div>
      ))}
    </>
  );
};

export default SlideOverCard;
