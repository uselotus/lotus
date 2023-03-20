import React from "react";
import { CheckCircleOutlined } from "@ant-design/icons";
import useGlobalStore from "../../stores/useGlobalstore";
import Badge from "../base/Badges/Badges";

interface SlideOverCardProps {
  switchOrg: (org_id: string) => void;
}

const SlideOverCard: React.FC<SlideOverCardProps> = ({ switchOrg }) => {
  const { linked_organizations } = useGlobalStore((state) => state.org);
  return React.Children.toArray(
    linked_organizations?.map((org) => (
      <div
        onClick={() => switchOrg(org.organization_id)}
        className={
          org.current
            ? "bg-[#C3986B1A] p-8 flex cursor-pointer mb-4"
            : "bg-gold-100 p-8 flex cursor-pointer mb-4"
        }
      >
        <div className="flex gap-2 items-center">
          <Badge.Dot
            fill={
              org.organization_type.toLowerCase() !== "production"
                ? "#60A5FA"
                : "#34D399"
            }
          />
          <span
            className={
              org.organization_type.toLowerCase() !== "production"
                ? "text-blue-800"
                : "text-emerald-800"
            }
          >
            {org.organization_name} Environment
          </span>
        </div>
        <div className="ml-auto">
          {org.current && <CheckCircleOutlined className="!text-gold" />}
        </div>
      </div>
    ))
  );
};

export default SlideOverCard;
