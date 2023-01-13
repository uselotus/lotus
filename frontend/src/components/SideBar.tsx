import React, { FC, useEffect } from "react";
import { Menu } from "antd";
import {
  HeartOutlined,
  UserOutlined,
  DashboardOutlined,
  SettingOutlined,
  BookOutlined,
  BorderlessTableOutlined,
  LineChartOutlined,
  LogoutOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";

import { useNavigate, useLocation } from "react-router-dom";
import { Authentication } from "../api/api";

const imgUrl = new URL("./Head.png", import.meta.url).href;

const formbricksEnabled =
  import.meta.env.VITE_FORMBRICKS_URL &&
  import.meta.env.VITE_FORMBRICKS_FORM_ID;

const SideBar: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [fbConfigReady, setFbConfigReady] = React.useState(false);

  const handleLogoutClick = () => {
    Authentication.logout().then(() => {
      window.location.reload();
      navigate("/");
    });
  };

  useEffect(() => {
    // set Formbricks Config
    if (formbricksEnabled) {
      window.formbricks = {
        config: {
          hqUrl: import.meta.env.VITE_FORMBRICKS_URL,
          formId: import.meta.env.VITE_FORMBRICKS_FORM_ID,
          contact: {
            name: "Mikael",
            position: "Co-Founder",
            imgUrl: "https://avatars.githubusercontent.com/u/33556500?v=4",
          },
          /* customer: {
            id: "abcdefg",
            name: "John Doe",
            email: "user@example.com",
          }, */
          style: {
            brandColor: "#c3986b",
            headerBGColor: "#1d1d1f",
            headerTitleColor: "#ffffff",
            boxBGColor: "#ffffff",
            textColor: "#374151",
            buttonHoverColor: "#EEEEF5",
            borderRadius: "4px",
          },
        },
        ...window.formbricks,
      };
      setFbConfigReady(true);
    }
  });

  useEffect(() => {
    if (fbConfigReady) {
      // load Formbricks feedback widget
      const script = document.createElement("script");
      script.src =
        "https://cdn.jsdelivr.net/npm/@formbricks/feedback@0.1.9/dist/index.umd.js";
      script.async = true;
      document.body.appendChild(script);
    }
  }, [fbConfigReady]);

  const menuItemsBasic: any = [
    {
      key: "/dashboard",
      icon: <DashboardOutlined />,
      label: "Dashboard",
      onClick: () => navigate("/dashboard"),
    },
    {
      key: "/experiments",
      icon: <ExperimentOutlined />,
      label: "Experiments",
      onClick: () => navigate("/experiments"),
    },
    {
      key: "/customers",
      icon: <UserOutlined />,
      label: "Customers",
      onClick: () => navigate("/customers"),
    },
    {
      key: "/plans",
      icon: <BorderlessTableOutlined />,
      label: "Plans",
      onClick: () => navigate("/plans"),
    },

    {
      key: "/metrics",
      icon: <LineChartOutlined />,

      label: "Metrics",
      onClick: () => navigate("/metrics"),
    },
    {
      type: "divider",
    },
    {
      label: "Docs",
      key: "/docs",
      icon: <BookOutlined />,
      onClick: () =>
        window.open(
          "https://docs.uselotus.io/docs/overview/why-lotus",
          "_blank"
        ),
    },
  ];

  const menuItemsAdmin: any = [
    {
      key: "/dashboard",
      icon: <DashboardOutlined />,
      label: "Dashboard",
      onClick: () => navigate("/dashboard"),
    },
    {
      key: "/experiments",
      icon: <ExperimentOutlined />,
      label: "Experiments",
      onClick: () => navigate("/experiments"),
    },
    {
      key: "/customers",
      icon: <UserOutlined />,
      label: "Customers",
      onClick: () => navigate("/customers"),
    },
    {
      key: "/plans",
      icon: <BorderlessTableOutlined />,
      label: "Plans",
      onClick: () => navigate("/plans"),
    },

    {
      key: "/metrics",
      icon: <LineChartOutlined />,
      label: "Metrics",
      onClick: () => navigate("/metrics"),
    },
    {
      type: "divider",
    },
    {
      label: "Docs",
      key: "/docs",
      icon: <BookOutlined />,
      onClick: () =>
        window.open(
          "https://docs.uselotus.io/docs/overview/why-lotus",
          "_blank"
        ),
    },
    {
      key: "/settings",
      icon: <SettingOutlined />,
      label: "Settings",
      onClick: () => navigate("/settings/general"),
    },
  ];

  // @ts-ignore
  const menuItems =
    import.meta.env.VITE_IS_DEMO === "true" ? menuItemsBasic : menuItemsAdmin;

  return (
    <div
      className="h-screen flex flex-col justify-between"
      style={{
        position: "fixed",
        zIndex: 1,
        width: "200px",
        borderRight: "1px solid #e8e8e8",
      }}
    >
      <div>
        <img src={imgUrl} alt="lotus" className="mb-4" />
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          style={{ background: "#fafafa" }}
        />
      </div>

      <div className="mb-5">
        <Menu
          style={{ background: "#fafafa" }}
          items={[
            {
              type: "divider",
            },
            formbricksEnabled && {
              key: "/feedback",
              icon: <HeartOutlined />,
              label: "Feedback",
              onClick: (e) => {
                window.formbricks.open(e.domEvent);
              },
            },
            {
              key: "/logout",
              icon: <LogoutOutlined />,
              label: "Logout",
              onClick: handleLogoutClick,
            },
          ]}
        />
      </div>
    </div>
  );
};

export default SideBar;
