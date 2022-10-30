import React, { FC } from "react";
import { Card, Col, Row, Tabs } from "antd";
import IntegrationsTab from "./tabs/IntegrationsTab";
import { PageLayout } from "../../components/base/PageLayout";
import { DeveloperTab } from "./tabs/DeveloperTab";
import TeamTab from "./tabs/TeamTab";

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
      </Tabs>
    </PageLayout>
  );
};

export default SettingsPage;
