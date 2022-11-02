import React, { FC } from "react";
import { Card, Col, Row, Tabs } from "antd";
import IntegrationsTab from "../components/Settings/settings/tabs/IntegrationsTab";
import { DeveloperTab } from "../components/Settings/settings/tabs/DeveloperTab";
import TeamTab from "../components/Settings/settings/tabs/TeamTab";
import { PageLayout } from "../components/base/PageLayout";
import ActivityStream from "../components/Settings/settings/tabs/ActivityTab";
import { Typography } from "antd";

const SettingsPage: FC = () => {
  return (
    <PageLayout title="Settings">
      <Tabs size="large">
        {/* <Tabs.TabPane tab="Profile" key="profile">
          Profile
        </Tabs.TabPane> */}
        <Tabs.TabPane tab="Integrations" key="integrations">
          <IntegrationsTab />
        </Tabs.TabPane>
        <Tabs.TabPane tab="Team" key="team">
          <TeamTab />
        </Tabs.TabPane>
        <Tabs.TabPane tab="Developer Settings" key="developer-settings">
          <DeveloperTab />
        </Tabs.TabPane>
        <Tabs.TabPane tab="Billing" key="billing">
          <Typography.Title level={2}>Billing</Typography.Title>
        </Tabs.TabPane>
        <Tabs.TabPane tab="Activity" key="activity">
          <ActivityStream />
        </Tabs.TabPane>
      </Tabs>
    </PageLayout>
  );
};

export default SettingsPage;
