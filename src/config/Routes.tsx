import React, { FC, useState, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "../components/Dashboard";
import ViewPlans from "../pages/ViewPlans";
import ViewCustomers from "../pages/ViewCustomers";
import ViewSettings from "../pages/ViewSettings";
import StripeRedirect from "../pages/StripeRedirect";

// import MainContent from "./components/MainContent";
import SideBar from "../components/SideBar";
import { Divider, Layout } from "antd";
import { MenuUnfoldOutlined, MenuFoldOutlined } from "@ant-design/icons";
import CreatePlan from "../pages/CreatePlan";

const { Header, Sider, Content, Footer } = Layout;

const AppRoutes: FC = () => {
  const [collapse, setCollapse] = useState(false);

  const handleToggle = (event: any) => {
    event.preventDefault();
    collapse ? setCollapse(false) : setCollapse(true);
  };

  useEffect(() => {
    window.innerWidth <= 760 ? setCollapse(true) : setCollapse(false);
  }, []);
  return (
    <div className="bg-darkgold">
      <Layout>
        <Sider
          trigger={null}
          collapsible={false}
          collapsed={collapse}
          style={{ minHeight: "100vh", background: "#000000" }}
        >
          <SideBar />
        </Sider>
        <Layout style={{ background: "#FFFFFF" }}>
          <Content
            style={{
              margin: "24px 16px",
              padding: 24,
              minHeight: "calc(100vh - 114px)",
              background: "#fff",
            }}
          >
            <Routes>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/" element={<Dashboard />} />
              <Route path="/plans" element={<ViewPlans />} />
              <Route path="create-plan" element={<CreatePlan />} />
              <Route path="/customers" element={<ViewCustomers />} />
              <Route path="/customers-create" element={<CreatePlan />} />
              <Route path="/settings" element={<ViewSettings />} />
              <Route path="/redirectstripe" element={<StripeRedirect />} />
            </Routes>
          </Content>
          <Footer style={{ textAlign: "center" }}>Lotus Tech Co. @2022</Footer>
        </Layout>
      </Layout>
    </div>
  );
};

export default AppRoutes;
