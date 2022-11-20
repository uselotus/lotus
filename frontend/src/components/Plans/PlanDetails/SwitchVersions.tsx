// @ts-ignore
import React, { FC, useEffect, useState, version } from "react";
import "./SwitchVersions.css";
import { PlusOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { PlanVersionType } from "../../../types/plan-type";
import PlanComponents from "./PlanComponent";
import PlanFeatures from "./PlanFeatures";
import StateTabs from "./StateTabs";
import { Dropdown, Menu, Button } from "antd";
import { MoreOutlined } from "@ant-design/icons";
// @ts-ignore
import dayjs from "dayjs";
import { DeleteOutlined } from "@ant-design/icons";
import { Plan } from "../../../api/api";
import { useMutation, useQueryClient } from "react-query";

interface SwitchVersionProps {
  versions: PlanVersionType[];
  className: string;
}

//function that takes in a string and returns a string based on the cases of the string equals percentage, flat, or override
function getPriceAdjustmentEnding(
  type: string | undefined,
  amount: number | undefined
) {
  switch (type) {
    case "percentage":
      return amount + "%";
    case "fixed":
      return "$ " + amount;
    case "price_override":
      return "$ " + amount;
    default:
      return "No Adjustment";
  }
}

function capitalize(word: string) {
  return word[0].toUpperCase() + word.slice(1).toLowerCase();
}

const SwitchVersions: FC<SwitchVersionProps> = ({ versions, className }) => {
  const activePlanVersion = versions.find((x) => x.status === "active");
  const [selectedVersion, setSelectedVersion] = useState(activePlanVersion);
  const [capitalizedState, setCapitalizedState] = useState<string>("");
  const queryClient = useQueryClient();

  const activeVersion = versions.find((x) => x.status === "active")?.version;

  const isSelectedVersion = (other_id: string) =>
    selectedVersion.version_id === other_id;

  const archivemutation = useMutation(
    (version_id: string) =>
      Plan.archivePlanVersion(version_id, { status: "archived" }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("plan_list");
      },
    }
  );

  useEffect(() => {
    setCapitalizedState(capitalize(selectedVersion.status));
  }, [selectedVersion.status]);

  const menu = (
    <Menu>
      <Menu.Item
        key="1"
        onClick={() => archivemutation.mutate(selectedVersion.version_id)}
        disabled={
          selectedVersion.status === "active" ||
          selectedVersion.status === "grandfathered"
        }
      >
        <div className="planMenuArchiveIcon">
          <div>
            <DeleteOutlined />
          </div>
          <div className="archiveLabel">Archive</div>
        </div>
      </Menu.Item>
    </Menu>
  );

  return (
    <div>
      <div className={className}>
        {versions.map((version) => (
          <div
            onClick={() => setSelectedVersion(version)}
            className={[
              "flex items-center justify-center versionChip mx-1",
              isSelectedVersion(version.version_id)
                ? "bg-[#c3986b] text-white opacity-100"
                : "bg-[#EAEAEB] text-black",
              version.status === "active" &&
                "border-2 border-[#c3986b] border-opacity-100",
            ].join(" ")}
          >
            v{version.version}
          </div>
        ))}
        <Link
          type="text"
          to={"/create-version/" + selectedVersion.plan_id}
          className="mx-4"
        >
          <div className="flex items-center justify-center px-2 py-2 rounded-[20px] hover:bg-[#EAEAEB]">
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
              activeTab={capitalizedState}
              version_id={selectedVersion.version_id}
              version={selectedVersion.version}
              activeVersion={activeVersion}
              tabs={["Active", "Grandfathered", "Retiring", "Inactive"]}
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
              <div className="infoValue">self</div>
            </div>
          </div>

          <div className="flex flex-col items-start w-30">
            <div className="flex items-center planInfo py-2">
              <div className="pr-2 infoLabel">Recurring Billing Type:</div>
              <div className="infoValue">
                {selectedVersion.flat_fee_billing_type}
              </div>
            </div>
            {/* <div className="flex items-center planInfo py-2 mt-2">
              <div className="pr-2 infoLabel">
                Components Billing Frequency:
              </div>
              <div className="infoValue">
                {" "}
                {selectedVersion.usage_billing_frequency}
              </div>
            </div> */}
          </div>
        </div>

        <div className="px-4 py-2">
          <PlanComponents components={selectedVersion.components} />
        </div>
        <div className="px-4 py-2">
          <PlanFeatures features={selectedVersion.features} />
        </div>

        <div className="separator pt-4" />

        <div className="px-4 py-4 flex justify-start align-middle ">
          <div className="pb-5 pt-3 font-main font-bold text-[20px]">
            Price Adjustments:
          </div>
          <div className="mb-5 mt-3 px-4 font-main font-bold text-[20px] self-center">
            {getPriceAdjustmentEnding(
              selectedVersion.price_adjustment?.price_adjustment_type,
              selectedVersion.price_adjustment?.price_adjustment_amount
            )}
          </div>
        </div>

        {/* <div className="px-4 py-4 flex items-center justify-between">
          <div className="pb-5 pt-3 font-main font-bold text-[20px]">
            Localisation:
          </div>
          <div>
            <Button size="large" key="use lotus recommended">
              Use Lotus Recommended
            </Button>
          </div>
        </div> */}
      </div>
    </div>
  );
};
export default SwitchVersions;
