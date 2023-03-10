/* eslint-disable no-shadow */
/* eslint-disable camelcase */
/* eslint-disable @typescript-eslint/no-non-null-assertion */

import React, { FC, useCallback, useEffect, useRef, useState } from "react";

import "./SwitchVersions.css";
import { PlusOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import { Typography, Dropdown, Select, Menu } from "antd";
import { useMutation, useQueryClient } from "react-query";
import { PlanType } from "../../../types/plan-type";
import PlanComponents, { PlanInfo, PlanSummary } from "./PlanComponent";
import PlanFeatures from "./PlanFeatures";

import { Plan } from "../../../api/api";
import PlanRecurringCharges from "./PlanRecurringCharges";
import PlanCustomerSubscriptions from "./PlanCustomerSubscriptions";
import { components } from "../../../gen-types";
import ChevronDown from "../../base/ChevronDown";
import DropdownComponent from "../../base/Dropdown/Dropdown";
import AddCurrencyModal from "./AddCurrencyModal";
import DeleteVersionModal from "./DeleteVersionModal";

interface SwitchVersionProps {
  versions: components["schemas"]["PlanDetail"]["versions"];
  plan: components["schemas"]["PlanDetail"];
  refetch: VoidFunction;
  activeKey: string;
  className: string;
  createPlanExternalLink: (link: string) => void;
  deletePlanExternalLink: (link: string) => void;
}

// function that takes in a string and returns a string based on the cases of the string equals percentage, flat, or override
function getPriceAdjustmentEnding(
  type: string | undefined,
  amount: number | undefined,
  code: string
) {
  switch (type) {
    case "percentage":
      return `${amount}%`;
    case "fixed":
      return `${code} ${amount}`;
    case "price_override":
      return `${code} ${amount}`;
    default:
      return "No discount added";
  }
}

function capitalize(word: string) {
  return word[0].toUpperCase() + word.slice(1).toLowerCase();
}

const SwitchVersions: FC<SwitchVersionProps> = ({
  versions,
  plan,
  refetch,
  activeKey,
  createPlanExternalLink,
  deletePlanExternalLink,
  className,
}) => {
  const activePlanVersion = versions.find((x) => x.status === "active");

  const [selectedVersion, setSelectedVersion] = useState<
    components["schemas"]["PlanDetail"]["versions"][0] | undefined
  >(activePlanVersion);
  const [dropDownVersions, setDropDownVersions] = useState<
    components["schemas"]["PlanDetail"]["versions"]
  >([]);
  const [deduplicatedVersions, setDeduplicatedVersions] = useState<
    components["schemas"]["PlanDetail"]["versions"]
  >([]);
  const [triggerCurrencyModal, setTriggerCurrencyModal] = useState(false);
  const selectRef = useRef<HTMLSelectElement | null>(null!);
  const [triggerDeleteModal, setTriggerDeleteModal] = useState(false);
  const [capitalizedState, setCapitalizedState] = useState<string>("");
  const queryClient = useQueryClient();
  const removeDuplicateVersions = useCallback(
    (versions: components["schemas"]["PlanDetail"]["versions"]) => {
      let seen: { [key: string]: boolean } = {};

      const arr = [...dropDownVersions, ...[selectedVersion]];
      if (versions.length === 1) {
        const newVersion = [selectedVersion];
        setDeduplicatedVersions(
          newVersion as components["schemas"]["PlanDetail"]["versions"]
        );
        setDropDownVersions(newVersion);
        return [];
      }

      const v = versions.filter((obj) => {
        if (seen[obj.version]) {
          arr.push(obj);

          return false;
          // eslint-disable-next-line no-else-return
        } else {
          seen[obj.version] = true;
          seen[obj.version_id] = true;
          return true;
        }
      });
      seen = {};
      setDropDownVersions(
        arr.filter((obj) => {
          if (seen[obj.version] && seen[obj?.version_id]) {
            return false;
            // eslint-disable-next-line no-else-return
          } else {
            seen[obj.version] = true;
            seen[obj?.version_id] = true;
            return true;
          }
        })
      );
      const newVersions = [...v];
      setDeduplicatedVersions(
        newVersions as components["schemas"]["PlanDetail"]["versions"]
      );
    },
    []
  );
  useEffect(() => {
    removeDuplicateVersions(versions);
  }, [selectedVersion, versions, removeDuplicateVersions]);
  const isSelectedVersion = (other_id: string) =>
    selectedVersion?.version_id === other_id;
  const createTag = useMutation(
    ({ plan_id, tags }: { plan_id: string; tags: PlanType["tags"] }) =>
      Plan.createTagsPlan(plan_id, {
        tags,
      }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("plan_list");
        queryClient.invalidateQueries(["plan_detail", plan.plan_id]);
      },
    }
  );
  const deleteTag = useMutation(
    ({ plan_id, tags }: { plan_id: string; tags: PlanType["tags"] }) =>
      Plan.removeTagsPlan(plan_id, {
        tags,
      }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries("plan_list");
        queryClient.invalidateQueries(["plan_detail", plan.plan_id]);
      },
    }
  );
  useEffect(() => {
    setSelectedVersion(plan.versions.find((x) => x.status === "active")!);
  }, [plan]);
  useEffect(() => {
    setCapitalizedState(capitalize(selectedVersion!.status));
  }, [selectedVersion?.status]);
  if (!activePlanVersion) {
    return <div>No Active Plan</div>;
  }

  return (
    <div>
      <div className={className}>
        {deduplicatedVersions.map((version) => (
          <div
            aria-hidden
            key={version?.version_id}
            onClick={() => {
              refetch();
              setSelectedVersion(version);
            }}
            className={[
              "flex items-center justify-center p-6 cursor-pointer mx-1 gap-4 h-33px",
              isSelectedVersion(version!.version_id)
                ? "bg-[#c3986b] text-white opacity-100 ml-2 mr-2"
                : "bg-[#EAEAEB] text-black ml-2 mr-2",
              version?.status === "active" &&
                "border-2 border-[#c3986b] border-opacity-100 ml-2 mr-2",
            ].join(" ")}
          >
            {/* v{version.version} <ChevronDown /> */}
            <Dropdown
              overlay={
                <Menu className="!bg-primary-50 !whitespace-nowrap">
                  <Menu.Item
                    key="1"
                    onClick={() => {
                      setTriggerCurrencyModal(true);
                      setTriggerDeleteModal(false);
                    }}
                  >
                    <span className="flex gap-2 justify-between ">
                      <span className="flex gap-2 items-center">
                        <span className="text-black">Add Currency</span>
                      </span>
                    </span>
                  </Menu.Item>
                  <Menu.Item
                    key="2"
                    onClick={() => {
                      setTriggerCurrencyModal(false);
                      setTriggerDeleteModal(true);
                    }}
                  >
                    <span className="flex gap-2 justify-between ">
                      <span className="flex gap-2 items-center">
                        <span className="text-black">Delete</span>
                      </span>
                    </span>
                  </Menu.Item>
                </Menu>
              }
            >
              <div className="flex gap-2 items-center">
                v{version.version}
                {/* {version.currency && `-${version.currency.symbol}`} */}
                <ChevronDown />
              </div>
            </Dropdown>
          </div>
        ))}
        <Link
          type="text"
          to={`/create-version/${selectedVersion?.plan_id}`}
          className="mx-4"
        >
          <div className="flex items-center justify-center px-2 py-2  hover:bg-[#EAEAEB] hover:bg-4">
            <div className="addVersionButton">
              <PlusOutlined />
            </div>
            <div className=" text-[#1d1d1f]">Add new version</div>
          </div>
        </Link>
        <div>
          <Select
            value={`Currency:${selectedVersion?.currency?.code}-${selectedVersion?.currency?.symbol}`}
            onChange={(e) => {
              // const arr = [
              //   ...[selectedVersion],
              //   ...removeDuplicateVersions(versions),
              // ];
              if (e.split("-")[0] === "undefined") {
                return;
              }
              const [versionNum, symbol] = e.split("-");
              const version = versionNum.split("v")[1];

              const newSelectedVersion = dropDownVersions.find(
                (el) =>
                  el?.version === Number(version) &&
                  el.currency &&
                  el.currency.symbol === symbol
              );

              if (newSelectedVersion) {
                setSelectedVersion(newSelectedVersion);
              }
            }}
          >
            {dropDownVersions.map((el) => (
              <Select.Option
                value={`${el?.currency?.code}-${el?.currency?.symbol}`}
                key={el?.version_id}
              >
                {`Currency:${el?.currency?.code}-${el?.currency?.symbol}`}
              </Select.Option>
            ))}
          </Select>
        </div>
      </div>
      <div className="bg-white mb-6 flex flex-col py-4 px-10 rounded-lg space-y-12">
        <div className="grid gap-12 grid-cols-1 -mx-10  md:grid-cols-3">
          <div className="col-span-1">
            <PlanSummary
              plan={plan}
              createPlanExternalLink={createPlanExternalLink}
              createTagMutation={createTag.mutate}
              deleteTagMutation={deleteTag.mutate}
              deletePlanExternalLink={deletePlanExternalLink}
            />
          </div>
          <div className="col-span-2">
            <PlanInfo
              activeKey={activeKey}
              plan={plan}
              version={selectedVersion!}
            />
          </div>
        </div>
        <div className="-mx-10">
          <PlanRecurringCharges
            recurringCharges={selectedVersion!.recurring_charges}
          />
        </div>
        <div className="-mx-10">
          <PlanComponents
            refetch={refetch}
            plan={plan}
            components={selectedVersion?.components}
            alerts={selectedVersion?.alerts}
            plan_version_id={selectedVersion!.version_id}
          />
        </div>
        <div className="-mx-10">
          <PlanFeatures features={selectedVersion?.features} />
        </div>
        <div className="-mx-10">
          <PlanCustomerSubscriptions
            plan_id={plan.plan_id}
            version_id={selectedVersion!.version_id}
          />
        </div>
      </div>
      <AddCurrencyModal
        plan_id={plan.plan_id}
        version_id={selectedVersion?.version_id as string}
        showModal={triggerCurrencyModal}
        setShowModal={(show) => setTriggerCurrencyModal(show)}
        version={selectedVersion?.version as number}
      />
      <DeleteVersionModal
        version_id={selectedVersion?.version_id as string}
        plan_id={plan.plan_id}
        showModal={triggerDeleteModal}
        setShowModal={(show) => setTriggerDeleteModal(show)}
      />
    </div>
  );
};
export default SwitchVersions;
