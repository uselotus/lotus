import React, { FC, useEffect, useState } from "react";
import CustomerTable from "../components/CustomerTable";
import { CustomerTableItem } from "../types/customer-type";
import { Customer } from "../api/api";
import * as Toast from "@radix-ui/react-toast";

const ViewCustomers: FC = () => {
  const [customers, setCustomers] = useState<CustomerTableItem[]>([]);

  useEffect(() => {
    Customer.getCustomers().then((data) => {
      setCustomers(data.customers);
    });
  }, []);

  return (
    <div>
      <h1 className="text-3xl font-main ">Customers</h1>
      <CustomerTable customerArray={customers} />
    </div>
  );
};

export default ViewCustomers;
