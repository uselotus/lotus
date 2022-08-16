import React, { FC } from "react";
import { Menu } from "antd";
import {
  UserOutlined,
  VideoCameraOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router";

const SideBar: FC = () => {
  const navigate = useNavigate();

  const handleCustomersClick = () => {
    navigate("/customers");
  };
  const handlePlansClick = () => {
    navigate("/plans");
  };
  const handleDashboardClick = () => {
    navigate("/dashboard");
  };
  const handleSettingsClick = () => {
    navigate("/settings");
  };

  return (
    <div>
      <div
        style={{
          height: "32px",
          background: "#fff",
          margin: "16px",
        }}
      >
        <img src={"../assets/images/logo_small.svg"} alt="lotus" />
      </div>
      <Menu theme="dark" mode="vertical" defaultSelectedKeys={["1"]}>
        <Menu.Item key="1" onClick={handleDashboardClick}>
          <UserOutlined />
          <span> Dashboard</span>
        </Menu.Item>
        <Menu.Item key="2" onClick={handleCustomersClick}>
          <VideoCameraOutlined />
          <span> Customers</span>
        </Menu.Item>
        <Menu.Item key="3" onClick={handlePlansClick}>
          <UploadOutlined />
          <span> Plans</span>
        </Menu.Item>
        <Menu.Item title="Settings" onClick={handleSettingsClick}>
          <span> Settings</span>
        </Menu.Item>
      </Menu>
    </div>
  );
};

export default SideBar;
