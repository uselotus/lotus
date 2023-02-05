// @ts-ignore
import React, { FC, Fragment, useEffect, useState } from "react";
import "./StateTabs.css";
import { Tooltip, Modal, Select } from "antd";
import { useMutation, useQueryClient } from "react-query";
import { Plan } from "../../../api/api";

interface StateTabsProps {
  tabs: string[];
  activeTab: string;
  version: number | string;
  version_id: string;
  activeVersion: number | string | undefined;
}

const StateTabs: FC<StateTabsProps> = ({
  tabs,
  activeTab,
  version,
  version_id,
  activeVersion,
}) => {
  const [currentActiveTab, setCurrentActiveTab] = useState(activeTab);
  const [visible, setVisible] = useState(false);
  const [activeType, setActiveType] = useState<
    "replace_on_active_version_renewal" | "grandfather_active"
  >("replace_on_active_version_renewal");
  const queryClient = useQueryClient();

  const mutation = useMutation(
    (version_id: string) =>
      Plan.replacePlanVersionLater(version_id, {
        status: "active",
        make_active_type: activeType,
      }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries(["plan_detail"]);
      },
    }
  );

  const setActiveModal = () => {
    setVisible(true);
  };

  useEffect(() => {
    setCurrentActiveTab(activeTab);
  }, [activeTab]);

  const getToolTipText = (tab) => {
    if (tab === currentActiveTab) {
      switch (tab) {
        case "Inactive":
          return "This version is not active and has no subscriptions";
        case "Active":
          return "This version is active and is the default version for new subscriptions";
        case "Grandfathered":
          return "This version has past subscriptions still on it.";
      }
    } else {
      switch (tab) {
        case "Inactive":
          return "Inactive";
        case "Active":
          return "If you make this version active, your other active version will become inactive.";
        case "Grandfathered":
          return "Grandfathered";
      }
    }
  };

  return (
    <div className="flex items-center w-full justify-between tabsContainer">
      {tabs.map((tab) => (
        <Tooltip title={getToolTipText(tab)}>
          <div
            onClick={() => {
              if (
                tab === "Active" &&
                currentActiveTab !== "Active" &&
                currentActiveTab !== "Retiring"
              ) {
                setActiveModal();
              }
            }}
            className={[
              "tabItem flex items-center",
              currentActiveTab === tab && "activeTab text-black",
            ].join(" ")}
          >
            {tab}
          </div>
        </Tooltip>
      ))}
      <Modal
        visible={visible}
        onOk={() => {
          mutation.mutate(version_id);
          setVisible(false);
        }}
        onCancel={() => {
          setVisible(false);
        }}
        title={`Are you sure you want to make v${  version  } active?`}
      >
        <div className="space-y-4 ">
          <div className="grid grid-row-3 items-center my-5">
            <h3 className="mb-6">
              How should subscriptions on the current active version be treated?
            </h3>
            <Select
              onChange={(value) => {
                setActiveType(value);
              }}
            >
              <Select.Option
                value="replace_on_active_version_renewal"
                className="my-3"
              >
                Migrate When Subscriptions Renew
              </Select.Option>
              <Select.Option value="grandfather_active">
                Grandfather Subscriptions, Do Not Migrate
              </Select.Option>
            </Select>
          </div>
          <div className="separator mb-6" />

          <h3 className="mb-8 font-bold">New Active Version: v{version}</h3>
          <div className="grid grid-cols-3">
            <h3>{activeTab}</h3>
            <h3>to</h3>
            <h3>Active</h3>
          </div>
          {activeVersion && (
            <>
              <h3 className="mb-8 font-bold">
                Current Active Version: v{activeVersion}
              </h3>
              <div className="grid grid-cols-3">
                <h3>Active</h3>
                <h3>to</h3>
                <h3>
                  {activeType === "replace_on_active_version_renewal"
                    ? "Retiring"
                    : "Grandfathered"}
                </h3>
              </div>
            </>
          )}
        </div>
      </Modal>
    </div>
  );
};
export default StateTabs;
