import React, { FC, useEffect, useState } from "react";
import SubscriptionTable from "../components/SubscriptionTable";
import { CustomerTableItem } from "../types/customer-type";
import { Customer } from "../api/api";
import * as Toast from "@radix-ui/react-toast";

const ViewSubscriptions: FC = () => {
  const [customers, setCustomers] = useState<CustomerTableItem[]>([]);

  useEffect(() => {
    Customer.getCustomers().then((data) => {
      setCustomers(data);
    });
  }, []);

  return (
    <div>
      <SubscriptionTable customerArray={customers} />
    </div>
  );
};

export default ViewSubscriptions;
