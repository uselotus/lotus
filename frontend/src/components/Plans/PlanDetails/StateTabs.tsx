// @ts-ignore
import React, { FC, useState } from "react";
import "./StateTabs.css";
import { Tooltip } from "antd";

interface StateTabsProps {
  tabs: string[];
  activeTab: string;
}

const StateTabs: FC<StateTabsProps> = ({ tabs, activeTab }) => {
  const [currentActiveTab, setCurrentActiveTab] = useState(activeTab);

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
          return "Make this version Inactive";
        case "Active":
          return "If you make this version active, your other active version will become inactive.";
        case "Grandfathered":
          return "Make this version Grandfathered";
      }
    }
  };

  return (
    <div className="flex items-center justify-around tabsContainer">
      {tabs.map((tab) => (
        <Tooltip title={getToolTipText(tab)}>
          <div
            // onClick={() => setCurrentActiveTab(tab)}
            className={[
              "tabItem flex items-center",
              currentActiveTab === tab && "activeTab text-black",
            ].join(" ")}
          >
            {tab}
          </div>
        </Tooltip>
      ))}
    </div>
  );
};
export default StateTabs;
