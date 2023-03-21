import React, { FC } from "react";
import { Menu, Progress } from "antd";
import {
  UserOutlined,
  DashboardOutlined,
  SettingOutlined,
  DatabaseOutlined,
  BookOutlined,
  BorderlessTableOutlined,
  LineChartOutlined,
  LogoutOutlined,
  ExperimentOutlined,
} from "@ant-design/icons";

import { useNavigate, useLocation } from "react-router-dom";
import { ItemType } from "antd/lib/menu/hooks/useItems";
import { Authentication } from "../api/api";
import useGlobalStore, { GlobalStoreState } from "../stores/useGlobalstore";
import { selectQuickStartProgress } from "../helpers/quickStartCheck";
const LotusHeader = () => (
  <svg
    width="81"
    height="23"
    viewBox="0 0 81 23"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M10.9237 0C4.89059 0 0 4.95412 0 11.0656C0 17.177 4.89059 22.1312 10.9237 22.1312C16.9558 22.1312 21.8473 17.177 21.8473 11.0656C21.8473 4.95412 16.9558 0 10.9237 0ZM7.50092 15.3931C6.47381 14.2799 5.59046 12.9491 5.10906 11.3999C4.62861 9.85076 4.60213 8.24793 4.81587 6.73803C5.80893 7.86279 6.67053 9.2012 7.15098 10.7494C7.63144 12.2986 7.67967 13.8947 7.50092 15.3931ZM12.4066 15.6528C11.981 16.5965 11.4656 17.4625 10.9407 18.2242C9.56743 16.3416 8.26511 13.8267 8.26511 11.0656C8.26511 8.3035 9.56743 5.78955 10.9407 3.90601C11.8496 5.22334 12.7254 6.85108 13.1689 8.65606C13.36 9.43017 13.4706 10.2369 13.4706 11.0656C13.4706 12.7096 13.0337 14.2655 12.4066 15.6528ZM16.5832 11.421C16.0422 12.9491 15.1295 14.2511 14.0939 15.3347C13.9397 13.819 14.0277 12.2172 14.5687 10.69C15.1087 9.16192 16.045 7.86758 17.1147 6.79551C17.2358 8.29966 17.1232 9.89387 16.5832 11.421Z"
      fill="#C3986B"
    />
    <path
      d="M27.8474 18.6237V3.32922H30.8672V18.6237H27.8474ZM31.3202 15.5646H37.9633V18.6237H33.0028L31.3202 15.5646Z"
      fill="#171412"
    />
    <path
      d="M44.3048 7.5246C45.0813 7.5246 45.8076 7.67501 46.4829 7.97297C47.1592 8.27188 47.7484 8.67618 48.2515 9.18683C48.7547 9.69652 49.1528 10.2943 49.4489 10.9784C49.7439 11.6634 49.8915 12.3915 49.8915 13.1637C49.8915 13.9359 49.743 14.6641 49.4489 15.3491C49.1538 16.0341 48.7547 16.6309 48.2515 17.1406C47.7484 17.6503 47.1592 18.0556 46.4829 18.3535C45.8067 18.6525 45.0813 18.8019 44.3048 18.8019C43.5283 18.8019 42.802 18.6515 42.1258 18.3535C41.4495 18.0546 40.8603 17.6513 40.3572 17.1406C39.854 16.6309 39.4539 16.0331 39.1608 15.3491C38.8657 14.6641 38.7181 13.9359 38.7181 13.1637C38.7181 12.3915 38.8647 11.6634 39.1608 10.9784C39.4558 10.2934 39.854 9.69652 40.3572 9.18683C40.8603 8.67714 41.4495 8.2738 42.1258 7.97297C42.802 7.67405 43.5283 7.5246 44.3048 7.5246ZM44.3048 16.1989C44.6642 16.1989 44.9981 16.1184 45.3083 15.9584C45.6175 15.7984 45.8909 15.5752 46.1283 15.2916C46.3657 15.008 46.5529 14.6794 46.6891 14.3086C46.8253 13.9369 46.8943 13.5326 46.8943 13.0957C46.8943 12.6876 46.8253 12.2986 46.6891 11.9278C46.5529 11.5561 46.3657 11.2361 46.1283 10.9659C45.8909 10.6967 45.6175 10.4821 45.3083 10.3221C44.999 10.1621 44.6642 10.0817 44.3048 10.0817C43.9454 10.0817 43.6078 10.1621 43.2909 10.3221C42.9741 10.4821 42.697 10.6977 42.4615 10.9659C42.2241 11.2352 42.0378 11.5561 41.9007 11.9278C41.7645 12.2996 41.6964 12.6895 41.6964 13.0957C41.6964 13.5326 41.7635 13.9378 41.9007 14.3086C42.0378 14.6803 42.2241 15.008 42.4615 15.2916C42.6989 15.5752 42.9751 15.7984 43.2909 15.9584C43.6078 16.1184 43.9454 16.1989 44.3048 16.1989Z"
      fill="#171412"
    />
    <path
      d="M55.1755 14.8882C55.1755 15.2235 55.2946 15.5071 55.532 15.7399C55.7694 15.9727 56.0522 16.0896 56.3832 16.0896H58.4752V18.6246H56.3832C55.8224 18.6246 55.2946 18.5193 54.7981 18.3085C54.3025 18.0977 53.8703 17.8065 53.5043 17.4347C53.1373 17.063 52.846 16.6309 52.6304 16.1337C52.4147 15.6384 52.3069 15.1067 52.3069 14.5385V11.261H50.754V8.8352H52.3069V4.88033H55.1755V14.8882ZM58.4762 8.8352V11.261H56.8797L55.5424 8.8352H58.4762Z"
      fill="#171412"
    />
    <path
      d="M65.9392 15.8712L66.9749 17.772V17.794C66.2267 18.4637 65.2999 18.799 64.1924 18.799C62.438 18.799 61.1943 18.3181 60.4613 17.3572C59.7851 16.4978 59.4474 15.1287 59.4474 13.249V7.69897H62.402V13.249C62.402 13.6428 62.4134 14.0212 62.4351 14.3853C62.4569 14.7493 62.5354 15.0703 62.6725 15.3472C62.8097 15.624 63.0206 15.8463 63.31 16.014C63.5975 16.1816 64.007 16.265 64.5395 16.265C64.7844 16.265 65.0209 16.2286 65.2517 16.1558C65.4815 16.0829 65.6971 15.9881 65.8986 15.8722H65.9392V15.8712ZM70.4685 7.69897V18.6898H67.5139V7.69897H70.4685Z"
      fill="#171412"
    />
    <path
      d="M77.0691 12.1348C77.5439 12.2948 77.978 12.4595 78.3743 12.6272C78.7696 12.7949 79.1148 12.9961 79.4099 13.2289C79.705 13.4617 79.9348 13.7414 80.1003 14.0691C80.2658 14.3967 80.349 14.7876 80.349 15.237V15.259C80.349 16.3665 79.9849 17.2326 79.2595 17.8592C78.5331 18.4857 77.5155 18.799 76.2065 18.799C75.3866 18.799 74.5817 18.6563 73.791 18.3689C73.0004 18.0814 72.2598 17.6752 71.5694 17.1454L71.5477 17.1234L71.5694 17.1013L73.0363 14.756L73.0581 14.778C73.4893 15.2446 73.9783 15.5981 74.525 15.8367C75.0716 16.0772 75.6542 16.1979 76.2718 16.1979C77.1202 16.1979 77.5448 15.9229 77.5448 15.3692C77.5448 15.1067 77.4086 14.9122 77.1353 14.7809C76.862 14.6497 76.5385 14.5261 76.1649 14.4092C76.0931 14.3805 76.024 14.3622 75.9597 14.3555C75.8954 14.3479 75.8263 14.3306 75.7554 14.3C75.3241 14.1831 74.8929 14.0566 74.4616 13.9187C74.0303 13.7807 73.6416 13.591 73.2964 13.3515C72.9512 13.1129 72.6665 12.8064 72.4452 12.4366C72.222 12.0667 72.1104 11.5906 72.1104 11.009V10.965C72.1104 10.4562 72.204 9.99159 72.3913 9.56908C72.5786 9.14849 72.8443 8.78443 73.1895 8.47977C73.5347 8.17415 73.9518 7.93942 74.4408 7.77176C74.9297 7.6041 75.4688 7.52075 76.0581 7.52075C76.7485 7.52075 77.4455 7.6271 78.1501 7.83787C78.8547 8.04864 79.5092 8.35905 80.1126 8.76719V8.81126L78.797 11.2361L78.7753 11.2141C78.4442 10.8787 78.0347 10.6124 77.5458 10.416C77.0568 10.2196 76.5395 10.1219 75.9928 10.1219C75.8925 10.1219 75.7772 10.1295 75.6476 10.1439C75.518 10.1583 75.3989 10.1947 75.291 10.2531C75.1832 10.3116 75.0924 10.3882 75.0205 10.4831C74.9487 10.5779 74.9127 10.713 74.9127 10.8864C74.9127 11.0177 74.9704 11.1384 75.0858 11.2476C75.2012 11.3568 75.3478 11.4593 75.5275 11.5532C75.7072 11.6481 75.9086 11.7381 76.1318 11.8272C76.355 11.9144 76.5744 11.9949 76.7901 12.0677C76.8336 12.0677 76.879 12.0754 76.9291 12.0897C76.9783 12.106 77.0256 12.1204 77.0691 12.1348Z"
      fill="#171412"
    />
  </svg>
);

const CustomQuickStartMenuItem = ({
  progressPercent = 0,
}: {
  progressPercent: number;
}) => (
  <div className="flex justify-start items-center">
    <BookOutlined />
    <span className="ml-1 mr-4">Quick Start</span>
    <Progress
      percent={progressPercent}
      strokeColor="#BF9F79"
      trailColor="#d7d5d5"
      showInfo={false}
      size="small"
    />
  </div>
);

const SideBar: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const totalProgress = useGlobalStore(selectQuickStartProgress);

  const handleLogoutClick = () => {
    Authentication.logout().then(() => {
      window.location.reload();
      navigate("/");
    });
  };

  const menuItemsBasic: ItemType[] = [
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
      key: "/add-ons",
      icon: <DatabaseOutlined />,
      label: "Add-ons",
      onClick: () => navigate("/add-ons"),
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

  const menuItemsAdmin: ItemType[] = [
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
      key: "/add-ons",
      icon: <DatabaseOutlined />,
      label: "Add-ons",
      onClick: () => navigate("/add-ons"),
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

  const menuItems =
    (import.meta as any).env.VITE_IS_DEMO === "true"
      ? menuItemsBasic
      : menuItemsAdmin;

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
        <div className="mt-[42px] ml-2 pl-10">
          <LotusHeader />
        </div>

        <div className="mt-24">
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            style={{ background: "#fafafa" }}
          />
        </div>
      </div>

      <div className="mb-5">
        <Menu
          style={{ background: "#fafafa" }}
          items={[
            {
              key: "/quickstart",
              icon: (
                <CustomQuickStartMenuItem progressPercent={totalProgress} />
              ),
              onClick: () => navigate("/quickstart"),
            },
            {
              type: "divider",
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
