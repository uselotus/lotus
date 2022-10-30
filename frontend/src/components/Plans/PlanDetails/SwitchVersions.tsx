// @ts-ignore
import React, { FC, useState } from "react";
import "./SwitchVersions.css";
import { PlusOutlined } from "@ant-design/icons";
import { useNavigate, Link } from "react-router-dom";
import { PlanVersionType } from "../../../types/plan-type";
import PlanComponents from "./PlanComponent";
import PlanFeatures from "./PlanFeatures";
import StateTabs from "./StateTabs";
import { Dropdown, Menu, Button } from "antd";
import { MoreOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
const menu = (
  <Menu>
    <Menu.Item key="1">Action 1</Menu.Item>
  </Menu>
);

interface SwitchVersionProps {
  versions: PlanVersionType[];
  className: string;
}

const SwitchVersions: FC<SwitchVersionProps> = ({ versions, className }) => {
  const [selectedVersion, setSelectedVersion] = useState(versions[0]);

  const isSelectedVersion = (other_id: string) =>
    selectedVersion.version_id === other_id;
  return (
    <div>
      <div className={className}>
        {versions.map((version) => (
          <div
            onClick={() => setSelectedVersion(version)}
            className={[
              "flex items-center justify-center versionChip mx-1",
              isSelectedVersion(version.version_id)
                ? "bg-[#c3986b] text-white"
                : "bg-[#EAEAEB] text-black",
            ].join(" ")}
          >
            Version {version.version}
          </div>
        ))}
        <Link type="text" to="/create-version" className="mx-4">
          <div className="flex items-center justify-center hover:bg-background">
            <div className="addVersionButton">
              <PlusOutlined />
            </div>
            <div className=" text-[#1d1d1f]">Add new version</div>
          </div>
        </Link>
      </div>
      <div className="bg-white mb-5 mx-10 py-4 px-10 rounded-lg">
        <div className="py-4 flex justify-between">
          <div className="text-2xl font-main px-4 flex items-center">
            <span className="pr-6">Plan Information</span>
            <StateTabs
              activeTab={"Inactive"}
              tabs={["Inactive", "Grandfathered", "Active"]}
            />
          </div>

          <div className="right-3" onClick={(e) => e.stopPropagation()}>
            <Dropdown overlay={menu} trigger={["click"]}>
              <Button
                type="text"
                size="small"
                onClick={(e) => e.preventDefault()}
              >
                <MoreOutlined />
              </Button>
            </Dropdown>
          </div>
        </div>
        <div className="separator" />
        <div className="px-4 py-2">
          <div className="planDetails">
            <div className="infoLabel">{selectedVersion.description}</div>
          </div>
        </div>

        <div className="flex items-center px-4 py-2">
          <div className="w-2/5">
            <div className="flex items-baseline py-2">
              <div className="planCost">${selectedVersion.flat_rate}</div>
              <div className="pl-2 infoLabel">Recurring price</div>
            </div>
            <div className="py-2">
              <div className="flex activeSubscriptions">
                <div className="pr-1">
                  Total Active Subscriptions:{" "}
                  {selectedVersion.active_subscriptions}
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col items-start w-30">
            <div className="flex items-center planInfo py-2">
              <div className="pr-2 infoLabel">Date Created:</div>
              <div className="infoValue">
                {" "}
                {dayjs(selectedVersion.created_on).format("YYYY/MM/DD")}
              </div>
            </div>
            <div className="flex items-center planInfo py-2 mt-2">
              <div className="pr-2 infoLabel">Plan on next cycle:</div>
              <div className="infoValue"> self</div>
            </div>
          </div>

          <div className="flex flex-col items-start w-30">
            <div className="flex items-center planInfo py-2">
              <div className="pr-2 infoLabel">Recurring Billing Type:</div>
              <div className="infoValue">
                {selectedVersion.flat_fee_billing_type}
              </div>
            </div>
            <div className="flex items-center planInfo py-2 mt-2">
              <div className="pr-2 infoLabel">
                Components Billing Frequency:
              </div>
              <div className="infoValue">
                {" "}
                {selectedVersion.usage_billing_frequency}
              </div>
            </div>
          </div>
        </div>

        <div className="px-4 py-2">
          <PlanComponents components={selectedVersion.components} />
        </div>
        <div className="px-4 py-2">
          <PlanFeatures features={selectedVersion.features} />
        </div>

        <div className="separator pt-4" />

        <div className="px-4 py-4 flex items-center justify-between">
          <div className="planDetails planComponentMetricName">
            Localisation:
          </div>
          <div>
            <Button size="large" key="use lotus recommended">
              Use Lotus Recommended
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
export default SwitchVersions;
